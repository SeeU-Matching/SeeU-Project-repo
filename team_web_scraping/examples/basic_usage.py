from job_scraper.service import JobScraperService

def example_1_basic_scraping():
    """Basic example: Scrape jobs and export to CSV."""
    print("=" * 60)
    print("Example 1: Basic Job Scraping")
    print("=" * 60)

    # Initialize the service
    scraper = JobScraperService()

    # Scrape and export to CSV
    output_file = scraper.scrape_and_export(
        job_title="Software Engineer",
        location="San Francisco",
        output_file="full_sf_engineers.csv",
        pages=None,
    )

    print(f"\n✓ Jobs exported to: {output_file}\n")


def example_2_get_jobs_as_data():
    """Get job data as Python list without exporting."""
    print("=" * 60)
    print("Example 2: Get Jobs as Data (no CSV)")
    print("=" * 60)

    scraper = JobScraperService()

    # Get jobs as list of dictionaries
    jobs = scraper.scrape_jobs(
        job_title="Data Scientist",
        location="New York",
        pages=1
    )

    # Process the data yourself
    print(f"\n✓ Found {len(jobs)} jobs")
    if jobs:
        print("\nFirst job:")
        for job in jobs:
            print(f" {job.title}({job.company}): {job.description[:100]}...")
    print()


def example_3_with_selenium():
    """Use Selenium for more reliable detail fetching (slower)."""
    print("=" * 60)
    print("Example 5: Using Selenium (Optional)")
    print("=" * 60)

    # Configure Selenium options if needed
    selenium_options = {
        "headless": True,  # Run in background
        # "driver_path": "/path/to/chromedriver",  # Optional: custom driver
        # "user_data_dir": "/path/to/chrome/data"   # Optional: custom user data
    }

    scraper = JobScraperService(selenium_options=selenium_options)

    # Use Selenium for detail fetching (more reliable but slower)
    output_file = scraper.scrape_and_export(
        job_title="Frontend Developer",
        location="Austin",
        output_file="frontend_selenium.csv",
        pages=1,
        use_selenium_for_details=True  # Enable Selenium
    )

    print(f"\n✓ Jobs scraped with Selenium exported to: {output_file}")
    print("  Note: Selenium is slower but may be more reliable\n")

def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("JOB SCRAPER - Usage Examples")
    print("=" * 60 + "\n")

    try:
        # Run examples
        example_2_get_jobs_as_data()
        example_1_basic_scraping()
        # example_3_with_selenium()

        print("=" * 60)
        print("All examples completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nError: {e}\n")

if __name__ == "__main__":
    main()
