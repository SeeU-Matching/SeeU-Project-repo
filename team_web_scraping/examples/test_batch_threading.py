import time
import logging
from job_scraper import ConcurrentJobScraperService
from job_scraper.utils.keyword_loader import load_job_keywords

logging.basicConfig(level=logging.INFO)

def test_medium():
    scraper = ConcurrentJobScraperService()

    KEYWORDS = load_job_keywords()

    job_titles = []

    for _, keywords in KEYWORDS.items():
        job_titles.extend(keywords[:1])

    print(f"Num of Job titles: {len(job_titles)}")

    locations = [
        "NY",
        "CA",
    ]

    print("Start testing")
    # calculate start time
    start_time = time.time()
    scraper.scrape_and_export_batch(
        job_titles=job_titles[:10],
        locations=locations,
        output_file="jobs_multithread.csv",
        pages=2,
        threads=8,
        proxy_file="proxies.json"
    )
    end_time = time.time()
    print(f"Multi-thread batch scraping completed in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    # test_simple()
    test_medium()
