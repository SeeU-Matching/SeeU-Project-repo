import time
import logging
from job_scraper import ConcurrentJobScraperService
from job_scraper.models.enums import States
from job_scraper.utils.keyword_loader import load_job_keywords

logging.basicConfig(level=logging.INFO)

def test_medium():
    scraper = ConcurrentJobScraperService()

    KEYWORDS = load_job_keywords()

    job_titles = []

    for _, keywords in KEYWORDS.items():
        job_titles.extend(keywords)

    print(f"Num of Job titles: {len(job_titles)}")

    locations = []
    for state in States:
        locations.append(state.value)

    print("Start testing")
    # calculate start time
    start_time = time.time()
    scraper.scrape_and_export_batch(
        job_titles=job_titles,
        locations=locations,
        output_file="jobs_multithread_full_2.csv",
        pages=None,
        threads=10,
        proxy_file="proxies.json"
    )
    end_time = time.time()
    print(f"Multi-thread batch scraping completed in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    # test_simple()
    test_medium()
