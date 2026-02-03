"""Service layer for concurrent job scraping operations."""

import logging
import concurrent.futures
import threading
import time
from queue import Queue
from typing import Iterable, Dict, Optional, Any, List
from job_scraper.core import BeautifulSoupScraper
from job_scraper.core import ProxyRateLimitError
from job_scraper.utils import save_jobs_to_csv
from job_scraper.utils.http import human_delay
from job_scraper.utils.proxy_manager import ProxyManager, load_proxies_from_json

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
        
        # We need a way to share the proxy manager or create new ones
        # For simplicity, we pass the raw proxies list and let threads instantiate/share manager if needed
        # Or better, create one manager here.
        # Note: ProxyManager might need to be thread-safe if shared. 
        # Assuming ProxyManager is simple, or we can instantiate one per thread if it just rotates lists.
        # Let's share one if it is read-only or simple state.
        main_proxy_manager = ProxyManager(proxies) if proxies else None

        # --- DEFINITIONS FOR WORKERS ---

        def search_worker_producer(task_item):
            """
            Producer: Scrapes listing pages for a (title, location) pair.
            Yields batches of results into the queue.
            """
            t_title, t_location = task_item
            
            # Retry logic setup
            max_retries = 2
            current_try = 0
            
            while current_try < max_retries:
                current_try += 1
                current_proxy = main_proxy_manager.get_proxy() if main_proxy_manager else None
                
                # Check proxy "cooldown" manually if we had access to logic, 
                # but here we rely on get_proxy returning a valid one or we wait?
                # For now, simplistic approach as in original code:
                if main_proxy_manager and not current_proxy and proxies:
                     logger.warning("All proxies in cooldown (search), waiting 10s...")
                     time.sleep(10)
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
                        experience_levels=experience_levels
                    ):
                        if page_results:
                            listing_queue.put(page_results)
                            found_any = True
                    
                    if not found_any:
                        logger.info("No new jobs found for %s in %s.", t_title, t_location)
                    
                    # Success
                    return

                except ProxyRateLimitError:
                    if main_proxy_manager and current_proxy:
                        logger.warning("Rate limit (Search) with proxy. Marking bad and retrying...")
                        main_proxy_manager.mark_bad(current_proxy)
                    else:
                        logger.warning("Rate limit (Search) without proxy. Retrying...")
                    
                    human_delay(5, 10)
                    continue

                except Exception as e:
                    logger.error("Error searching %s in %s: %s", t_title, t_location, e)
                    return

        def detail_worker_consumer():
            """
            Consumer: Pops listing batches from queue, fetches details, and writes to CSV.
            """
            # Each consumer gets its own scraper instance (and session)
            # It can reuse it across multiple batches
            current_proxy = main_proxy_manager.get_proxy() if main_proxy_manager else None
            
            # We don't need the cache/lock for details fetching as it was already deduped during search
            scraper = BeautifulSoupScraper(
                timeout=self.timeout,
                proxies=current_proxy
            )

            while True:
                batch = listing_queue.get()
                
                if batch is None:
                    # Poison pill: Stop signal
                    listing_queue.task_done()
                    break
                
                max_retries = 3
                current_try = 0
                
                while current_try < max_retries:
                    current_try += 1
                    try:
                        # Fetch details
                        detailed_jobs = scraper.fetch_details(batch)
                        
                        if detailed_jobs:
                            with csv_write_lock:
                                save_jobs_to_csv(detailed_jobs, output_file, mode="a", write_header=False)
                            logger.info("Saved %d detailed jobs (Consumer Pipeline)", len(detailed_jobs))
                        
                        # If successful, break retry loop
                        break
                        
                    except ProxyRateLimitError:
                        logger.warning("Rate limit hit in Detail Consumer (Try %d/%d).", current_try, max_retries)
                        
                        if main_proxy_manager and current_proxy:
                            main_proxy_manager.mark_bad(current_proxy)
                            logger.info("Marked proxy bad. Switching proxy...")
                        
                        # Wait before retry
                        human_delay(5, 10)
                        
                        # Get new proxy
                        current_proxy = main_proxy_manager.get_proxy() if main_proxy_manager else None
                        
                        # Update scraper with new proxy (need to recreate or update session)
                        # Recreating safe to ensure clean session
                        scraper = BeautifulSoupScraper(
                            timeout=self.timeout,
                            proxies=current_proxy
                        )
                        continue
                        
                    except Exception as e:
                        logger.error("Error in detail consumer: %s", e)
                        # Non-retryable error (or unknown), break to avoid infinite loop on bad data
                        break
                
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
        logger.info("Search Threads: %d, Detail Threads: %d", search_threads_count, detail_threads_count)

        detail_executor = concurrent.futures.ThreadPoolExecutor(max_workers=detail_threads_count)
        detail_futures = []
        for _ in range(detail_threads_count):
            detail_futures.append(detail_executor.submit(detail_worker_consumer))

        # 2. Run Producer Pool (Searchers)
        # We block here until all SEARCHING is done.
        # Consumers are running in background processing data as it arrives.
        with concurrent.futures.ThreadPoolExecutor(max_workers=search_threads_count) as search_executor:
            search_executor.map(search_worker_producer, work_items)

        logger.info("All search tasks completed. Waiting for consumers to finish queue...")

        # 3. Shutdown Consumers
        # Send poison pills (None) - one for each consumer thread
        for _ in range(detail_threads_count):
            listing_queue.put(None)
            
        # Wait for consumers to finish gracefully
        detail_executor.shutdown(wait=True)
        
        logger.info("Batch scrape completed. Results saved to %s", output_file)

        return output_file
