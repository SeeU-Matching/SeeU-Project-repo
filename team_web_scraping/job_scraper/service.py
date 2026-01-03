"""High-level service layer for job scraping operations."""

from typing import List, Dict, Optional, Any
from .core.beautifulsoup_scraper import BeautifulSoupScraper
from .core.selenium_scraper import SeleniumJobScraper
from .utils.save_csv import save_jobs_to_csv
from .models.job import JobResult


class JobScraperService:
    """Main service for job scraping operations that other projects can import."""

    def __init__(self,
                 timeout: int = 10,
                 selenium_options: Optional[Dict[str, Any]] = None):
        """
        Initialize the job scraper service.
        
        Args:
            timeout: Request timeout in seconds for BeautifulSoup scraper
            selenium_options: Optional dict of Selenium configuration
                - driver_path: Path to chromedriver
                - user_data_dir: Chrome user data directory
                - headless: Run in headless mode (default: True)
        """
        self.bs_scraper = BeautifulSoupScraper(timeout=timeout)
        self.selenium_options = selenium_options or {}

    def scrape_jobs(self,
                    job_title: str,
                    location: str,
                    pages: int = 1,
                    use_selenium_for_details: bool = False,
                    time_filter: str = "r86400",
                    experience_levels: str = "1,2,3") -> List[JobResult]:
        """
        Scrape jobs from LinkedIn.
        
        Args:
            job_title: Job title/keywords to search
            location: Location to search in
            pages: Number of pages to fetch (25 results per page)
            use_selenium_for_details: If True, use Selenium for detail fetching
            time_filter: Time filter (r86400=24h, r604800=week, r2592000=month)
            experience_levels: Comma-separated levels (1=internship, 2=entry, 3=associate)
        
        Returns:
            List of job dictionaries with all details
        """
        # Step 1: Get job listings (always use BeautifulSoup - fast)
        print(f"Fetching job listings for '{job_title}' in '{location}'...")
        listings = self.bs_scraper.get_listings(
            job_title=job_title,
            location=location,
            pages=pages,
            time_filter=time_filter,
            experience_levels=experience_levels
        )

        if not listings:
            print("No job listings found.")
            return []

        print(f"Found {len(listings)} job listings.")

        # Step 2: Fetch details
        if use_selenium_for_details:
            print("Fetching job details using Selenium...")
            try:
                with SeleniumJobScraper(**self.selenium_options) as selenium_scraper:
                    jobs = selenium_scraper.fetch_details(listings)
            except ValueError as e:
                print("Failed to initialize Selenium: ", e)
                print("Use BeautifulSoup instead")
                jobs = self.bs_scraper.fetch_details(listings)
        else:
            print("Fetching job details using BeautifulSoup...")
            jobs = self.bs_scraper.fetch_details(listings)

        print(f"Successfully scraped {len(jobs)} jobs.")
        return jobs

    def scrape_and_export(self,
                         job_title: str,
                         location: str,
                         output_file: str,
                         pages: int = 1,
                         use_selenium_for_details: bool = False,
                         time_filter: str = "r86400",
                         experience_levels: str = "1,2,3") -> str:
        """
        Scrape jobs and export to CSV file.
        
        This is the main method other projects should use.
        
        Args:
            job_title: Job title/keywords to search
            location: Location to search in
            output_file: Path to output CSV file
            pages: Number of pages to fetch (25 results per page)
            use_selenium_for_details: If True, use Selenium for detail fetching
            time_filter: Time filter (r86400=24h, r604800=week, r2592000=month)
            experience_levels: Comma-separated levels (1=internship, 2=entry, 3=associate)
        
        Returns:
            Path to the created CSV file
        """
        # Scrape jobs
        jobs = self.scrape_jobs(
            job_title=job_title,
            location=location,
            pages=pages,
            use_selenium_for_details=use_selenium_for_details,
            time_filter=time_filter,
            experience_levels=experience_levels
        )

        if not jobs:
            print("No jobs to export.")
            return output_file

        # Export to CSV
        print(f"Exporting to {output_file}...")
        save_jobs_to_csv(jobs, output_file)
        print(f"Successfully exported {len(jobs)} jobs to {output_file}")

        return output_file
