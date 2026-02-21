import time
import logging
from job_scraper import ConcurrentJobScraperService
from job_scraper.models.enums import States
from job_scraper.utils.keyword_loader import load_job_keywords
from job_scraper.core.sponsor_checker import SponsorChecker
from job_scraper.utils.save_csv import load_jobs_from_csv, save_jobs_to_csv

logging.basicConfig(level=logging.INFO)

def test_medium():
    scraper = ConcurrentJobScraperService()

    KEYWORDS = load_job_keywords()

    job_titles = []

    for catgory, keywords in KEYWORDS.items():
        job_titles.append((catgory.value, keywords[0]))

    print(f"Num of Job titles: {len(job_titles)}")

    locations = []
    for state in States:
        locations.append(state.value)

    print("Start testing")
    # calculate start time
    start_time = time.time()
    scraper.scrape_and_export_batch(
        job_titles=job_titles[3:4],
        locations=locations[:2],
        output_file="jobs_multithread_small.csv",
        pages=1,
        detail_threads=10,
        search_threads=2,
        proxy_file="proxies.json"
    )
    end_time = time.time()
    print(f"Multi-thread batch scraping completed in {end_time - start_time:.2f} seconds.")

    jobs = load_jobs_from_csv("jobs_multithread_small.csv")
    start_time = time.time()
    sc = SponsorChecker()
    for job in jobs:
        result = sc.check(job.company)
        job.h1b_sponsored = "Yes" if result["h1b"] else "Unknown"
        job.e_verified = "Yes" if result["everify"] else "Unknown"

    end_time = time.time()
    print(f"Processing h1b info completed in {end_time - start_time:.2f} seconds.")
    save_jobs_to_csv(jobs, "jobs_multithread_small.csv")



if __name__ == "__main__":
    # test_simple()
    test_medium()
