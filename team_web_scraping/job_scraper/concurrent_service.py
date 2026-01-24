"""Service layer for concurrent job scraping operations."""

import logging
import concurrent.futures
import threading
import time
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
        threads: int = 4,
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
            proxies: Optional list of proxies to use
            proxy_file: Optional path to JSON file containing proxies
        """

        # Initialize output file with headers (clears existing file)
        save_jobs_to_csv([], output_file, mode="w", write_header=True)

        write_lock = threading.Lock()
        # Global cache and lock for job IDs to prevent duplicate scraping across threads
        global_job_id_lock = threading.Lock()
        global_job_id_cache = set()

        # Create work items
        work_items = [(title, loc) for title in job_titles for loc in locations]

        # Initialize proxy manager
        if proxy_file and not proxies:
            proxies = load_proxies_from_json(proxy_file)
        
        proxy_manager = ProxyManager(proxies) if proxies else None

        def process_item(item):
            t_title, t_location = item
            
            # Retry logic for rate limiting
            max_retries = 2
            current_try = 0
            
            while current_try < max_retries:
                current_try += 1
                current_proxy = None
                
                try:
                    # Get proxy if manager exists
                    if proxy_manager:
                        current_proxy = proxy_manager.get_proxy()
                        if not current_proxy and proxies:
                            # If we have proxies but all are bad/cooldown, wait a bit and try again or proceed without
                            # For now, let's log and wait
                            logger.warning("All proxies in cooldown, waiting 10s...")
                            time.sleep(10)
                            current_proxy = proxy_manager.get_proxy()

                    # Instantiate a NEW scraper for this thread (new session)
                    thread_scraper = BeautifulSoupScraper(
                        timeout=self.timeout,
                        proxies=current_proxy,
                        job_id_cache=global_job_id_cache,
                        job_id_lock=global_job_id_lock
                    )

                    # 1. Get Listings
                    # listings are now guaranteed to be unique and "claimed" by this thread
                    # because we passed the shared cache and lock.
                    listings = thread_scraper.get_listings(
                        job_title=t_title,
                        location=t_location,
                        pages=pages,
                        time_filter=time_filter,
                        experience_levels=experience_levels
                    )
                    
                    # If successful, we break the retry loop
                    break

                except ProxyRateLimitError:
                    if proxy_manager and current_proxy:
                        logger.warning("Rate limit hit with proxy. \
                                       Marking bad and retrying ( %s / %s)...", current_try, max_retries)
                        proxy_manager.mark_bad(current_proxy)
                    else:
                         logger.warning("Rate limit hit without proxy (or manager). \
                                        Retrying ( %s / %s )...", current_try, max_retries)

                    if current_try >= max_retries:
                        logger.error("Max retries reached for {t_title} \
                                     in {t_location}. Skipping.")
                        return
 
                    human_delay(5, 10) # Wait a bit before retry
                    continue
                
                except Exception as e:
                    logger.error("Error processing %s in %s: %s", t_title, t_location, e)
                    return
            
            # Proceed with processing listings if we have them
            if not listings:
                return

            # 2. Results are already deduplicated by the scraper's shared cache
            unique_listings = listings

            if not unique_listings:
                logger.info("No new jobs found for %s \
                            in %s (all duplicates).", t_title, t_location)
                return

            # 3. Fetch Details for Unique Jobs
            logger.info("Fetching details for %d unique jobs for %s in %s...", 
                        len(unique_listings), t_title, t_location)

            detailed_jobs = thread_scraper.fetch_details(unique_listings)

            if not detailed_jobs:
                return

            # 4. Thread-Safe Write to CSV
            with write_lock:
                try:
                    save_jobs_to_csv(detailed_jobs, output_file, mode="a", write_header=False)
                    logger.info("Saved %d jobs for %s \
                                in %s", len(detailed_jobs), t_title, t_location)

                except Exception as e:
                    logger.error("Error processing %s in\n"
                    " %s: %s", t_title, t_location, e, exc_info=True)
                finally:
                    human_delay()

        # Execute with thread pool
        logger.info("Starting batch scrape with %s \
                    threads for %s tasks...", threads, len(work_items))
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            executor.map(process_item, work_items)

        logger.info("Batch scrape completed. Results saved to %s", output_file)

        return output_file
