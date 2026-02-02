import time
import logging
from job_scraper.service import JobScraperService
from job_scraper.utils.keyword_loader import load_job_keywords

logging.basicConfig(level=logging.INFO)

def test_simple():
    scraper = JobScraperService()

    job_titles = [
        "software engineer",
        "product manager"
    ]

    locations = [
        "New York, NY",
    ]

    # calculate start time
    start_time = time.time()
    scraper.scrape_and_export_batch(
        job_titles=job_titles,
        locations=locations,
        output_file="jobs.csv",
        pages=1
    )
    end_time = time.time()
    print(f"Batch scraping completed in {end_time - start_time:.2f} seconds.")

def test_medium():
    scraper = JobScraperService()

    KEYWORDS = load_job_keywords()

    job_titles = []

    i = 0
    for _, keywords in KEYWORDS.items():
        job_titles.extend(keywords)
        i += 1
        if i >= 2:
            break

    print(f"Num of Job titles: {len(job_titles)}")

    locations = [
        "New York, NY",
        # "San Francisco, CA",
    ]

    print("Start testing")
    # calculate start time
    start_time = time.time()
    scraper.scrape_and_export_batch(
        job_titles=job_titles,
        locations=locations,
        output_file="jobs_medium.csv",
        pages=1
    )
    end_time = time.time()
    print(f"Batch scraping completed in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    # test_simple()
    test_medium()
