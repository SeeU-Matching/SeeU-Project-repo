import time
from job_scraper.service import JobScraperService
from concurrent.futures import ThreadPoolExecutor
from job_scraper.utils.keyword_loader import load_job_keywords

def run_scrape_for_location(job_titles, location, output_file):
    """
    Function that runs a scrape for a single location.
    Designed to be executed in parallel.
    """
    scraper = JobScraperService()

    print(f"Starting scrape for: {location}")

    start = time.time()

    scraper.scrape_and_export_batch(
        job_titles=job_titles,
        locations=[location],
        output_file=output_file,
        pages=1
    )

    end = time.time()

    print(f"Finished {location} in {end - start:.2f} seconds.")


def test_parallel():

    KEYWORDS = load_job_keywords()

    job_titles = []

    i = 0
    for _, keywords in KEYWORDS.items():
        job_titles.extend(keywords)
        i += 1
        if i >= 2:
            break

    locations = [
        "New York, NY",
        "San Francisco, CA"
    ]

    start_time = time.time()

    # Run two locations in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(
            run_scrape_for_location,
            job_titles=job_titles,
            location=locations[0],
            output_file=f"{locations[0].lower().replace(',', '').replace(' ', '_')}.csv"
        )

        executor.submit(
            run_scrape_for_location,
            job_titles=job_titles,
            location=locations[1],
            output_file=f"{locations[1].lower().replace(',', '').replace(' ', '_')}.csv"

        )

    end_time = time.time()

    print(f"\nTotal parallel execution time: {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    test_parallel()