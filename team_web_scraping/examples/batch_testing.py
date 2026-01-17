from job_scraper.service import JobScraperService


def test_simple():
    scraper = JobScraperService()

    job_titles = [
        "software engineer",
        "data scientist",
        "product manager"
    ]

    locations = [
        "New York, NY",
        "San Francisco, CA",
    ]

    scraper.scrape_and_export_batch(
        job_titles=job_titles,
        locations=locations,
        output_file="jobs.csv",
        pages=1
    )

if __name__ == "__main__":
    test_simple()
