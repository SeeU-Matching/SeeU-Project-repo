"""Service layer for concurrent job scraping operations."""

import logging
import concurrent.futures
import threading
import time
from queue import Queue, Empty
from typing import Iterable, Dict, Optional, Any, List
from job_scraper.core import BeautifulSoupScraper
from job_scraper.core import ProxyRateLimitError
from job_scraper.utils import save_jobs_to_csv
from job_scraper.utils.proxy_manager import ProxyManager, load_proxies_from_json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random,
    retry_if_exception_type,
    Retrying,
    RetryError,
    before_sleep_log
)

logger = logging.getLogger(__name__)

class ConcurrentJobScraperService:
    """Service for batch job scraping operations using multithreading."""

    def __init__(
        self,
        timeout: int = 10,
        selenium_options: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the concurrent job scraper service.
        
        Args:
            timeout: Request timeout in seconds for BeautifulSoup scraper
            selenium_options: Optional dict of Selenium configuration (passed if needed in future)
        """
        self.timeout = timeout
        self.selenium_options = selenium_options or {}
        self.stop_event = threading.Event()

    def scrape_and_export_batch(
        self,
        job_titles: Iterable[str],
        locations: Iterable[str],
        output_file: str,
        pages: int = 1,
        time_filter: str = "r86400",
        experience_levels: str = "1,2,3",
        detail_threads: int = 4,
        search_threads: int = 1,
        proxies: Optional[List[Dict[str, str]]] = None,
        proxy_file: Optional[str] = None
    ) -> str:
        """
        Scrape jobs for multiple keywords and export to CSV file using multithreading.
        
        Args:
            job_titles: List of job titles/keywords to search
            locations: List of locations to search in
            output_file: Path to output CSV file
            pages: Number of pages to fetch (25 results per page)
            time_filter: Time filter (r86400=24h, r604800=week, r2592000=month)
            experience_levels: Comma-separated levels (1=internship, 2=entry, 3=associate)
            threads: Number of concurrent threads to use (default: 4)
            detail_threads: Number of concurrent threads for fetching job details (default: 4)
            search_threads: Number of concurrent threads for searching job listings (default: 1)
            proxies: Optional list of proxies to use
            proxy_file: Optional path to JSON file containing proxies
        """

        # Initialize output file with headers (clears existing file)
        save_jobs_to_csv([], output_file, mode="w", write_header=True)

        # Thread-safe resources
        csv_write_lock = threading.Lock()
        global_job_id_lock = threading.Lock()
        global_job_id_cache = set()

        # Communication channel between Search (Producer) and Detail (Consumer)
        # Queue item: List[Dict] (a page of listings) or None (poison pill)
        listing_queue = Queue()

        # Initialize proxy manager
        if proxy_file and not proxies:
            proxies = load_proxies_from_json(proxy_file)
            logger.warning("%s proxies loaded", len(proxies))

        main_proxy_manager = ProxyManager(proxies) if proxies else None

        # --- DEFINITIONS FOR WORKERS ---

        def search_worker_producer(task_item):
            """
            Producer: Scrapes listing pages for a (title, location) pair.
            Yields batches of results into the queue.
            """
            if self.stop_event.is_set():
                return
            _execute_search_task(task_item)

        @retry(
            retry=retry_if_exception_type(ProxyRateLimitError),
            stop=stop_after_attempt(2),
            wait=wait_random(min=5, max=10),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def _execute_search_task(task_item):
            t_title, t_location = task_item
            current_proxy = main_proxy_manager.get_proxy() if main_proxy_manager else None

            if main_proxy_manager and not current_proxy and proxies:
                # If no proxy available, wait briefly (though tenacity wait might cover this, 
                # this is pre-check for pool exhaustion)
                logger.warning("All proxies in cooldown (search), waiting...")
                time.sleep(5)
                current_proxy = main_proxy_manager.get_proxy()

            try:
                # Create scraper for this search task
                scraper = BeautifulSoupScraper(
                    timeout=self.timeout,
                    proxies=current_proxy,
                    job_id_cache=global_job_id_cache,
                    job_id_lock=global_job_id_lock
                )

                found_any = False
                # Stream pages into queue
                for page_results in scraper.yield_listings_pages(
                    job_title=t_title,
                    location=t_location,
                    pages=pages,
                    time_filter=time_filter,
                    experience_levels=experience_levels,
                ):
                    if self.stop_event.is_set():
                        break

                    if page_results:
                        # Inject search context into each result
                        for job in page_results:
                            job["search_title"] = t_title
                            job["search_location"] = t_location
                        listing_queue.put(page_results)
                        found_any = True

                if not found_any:
                    logger.info("No new jobs found for %s in %s.", t_title, t_location)

            except ProxyRateLimitError:
                if main_proxy_manager and current_proxy:
                    logger.warning("Rate limit (Search) with proxy. Marking bad.")
                    main_proxy_manager.mark_bad(current_proxy)
                # Re-raise to trigger Tenacity retry
                raise

            except Exception as e:
                logger.error("Error searching %s in %s: %s", t_title, t_location, e)
                # Valid non-retryable error, stop this task
                return

        def detail_worker_consumer():
            """
            Consumer: Pops listing batches from queue, fetches details, and writes to CSV.
            """
            current_proxy = main_proxy_manager.get_proxy() if main_proxy_manager else None
            scraper = BeautifulSoupScraper(
                timeout=self.timeout,
                proxies=current_proxy
            )

            while not self.stop_event.is_set():
                try:
                    # Use timeout to check stop_event periodically if queue is empty
                    batch = listing_queue.get(timeout=1.0)
                except Empty:
                    # Empty queue, check stop event loop
                    continue

                if batch is None:
                    listing_queue.task_done()
                    break

                try:
                    for attempt in Retrying(
                        retry=retry_if_exception_type(ProxyRateLimitError),
                        stop=stop_after_attempt(3),
                        wait=wait_random(min=5, max=10),
                        before_sleep=before_sleep_log(logger, logging.WARNING)
                    ):
                        with attempt:
                            try:
                                detailed_jobs = scraper.fetch_details(batch)

                                if detailed_jobs:
                                    with csv_write_lock:
                                        save_jobs_to_csv(detailed_jobs, output_file, mode="a", write_header=False)
                                    logger.info("Saved %d detailed jobs (Consumer Pipeline)", len(detailed_jobs))

                            except ProxyRateLimitError:
                                logger.warning("Rate limit hit in Detail Consumer. Rotating proxy.")

                                if main_proxy_manager and current_proxy:
                                    main_proxy_manager.mark_bad(current_proxy)

                                current_proxy = main_proxy_manager.get_proxy() \
                                    if main_proxy_manager else None

                                # Recreate scraper with new proxy (new session)
                                scraper = BeautifulSoupScraper(
                                    timeout=self.timeout,
                                    proxies=current_proxy
                                )
                                raise # Trigger tenacity retry

                except RetryError:
                    logger.error("Failed to fetch details for batch after retries. Skipping.")
                except Exception as e:
                    logger.error("Error in detail consumer: %s", e)

                listing_queue.task_done()

        # --- EXECUTION PHASE ---

        work_items = [(title, loc) for title in job_titles for loc in locations]

        # 1. Start Consumer Pool (Detail Fetchers)
        # We'll use the same number of threads for fetching as searching, or maybe slightly more?
        # User asked for "threadpool of search... and threadpool of fetching".
        # Let's use `threads` count for BOTH pools (e.g. 4 searchers, 4 fetchers).
        detail_threads_count = detail_threads
        search_threads_count = search_threads

        logger.info("Starting Batch Scrape (Producer-Consumer).")
        logger.info("Search Threads: %d, Detail Threads: %d",\
                     search_threads_count, detail_threads_count)

        detail_executor = concurrent.futures.ThreadPoolExecutor(max_workers=detail_threads_count)
        detail_futures = []
        for _ in range(detail_threads_count):
            detail_futures.append(detail_executor.submit(detail_worker_consumer))


        # 2. Run Producer Pool (Searchers)
        # We use submit instead of map to keep track of futures for cancellation
        search_futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=search_threads_count) as search_executor:
            try:
                for item in work_items:
                    search_futures.append(search_executor.submit(search_worker_producer, item))

                # Wait for all search tasks to complete
                concurrent.futures.wait(search_futures)

            except KeyboardInterrupt:
                logger.warning("Interrupted by user (Ctrl-C). Stopping services...")
                self.stop_event.set()

                # Cancel pending search tasks
                cancelled_count = 0
                for f in search_futures:
                    if f.cancel():
                        cancelled_count += 1
                logger.warning("Cancelled %d pending search tasks.", cancelled_count)
                raise

        # Determine if we finished naturally or were stopped
        if self.stop_event.is_set():
            logger.info("Service stopped. Waiting for graceful shutdown of threads...")
        else:
            logger.info("All search tasks completed. Waiting for consumers to finish queue...")

        # 3. Shutdown Consumers
        # Send poison pills (None) - one for each consumer thread
        # If stopping, consumers see stop_event.
        if not self.stop_event.is_set():
            for _ in range(detail_threads_count):
                listing_queue.put(None)

        # Wait for consumers to finish gracefully
        detail_executor.shutdown(wait=True)

        if self.stop_event.is_set():
            logger.info("Batch scrape stopped incomplete.")
        else:
            logger.info("Batch scrape completed. Results saved to %s", output_file)

        return output_file
