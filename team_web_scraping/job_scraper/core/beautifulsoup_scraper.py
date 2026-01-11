"""BeautifulSoup-based scraper for LinkedIn job listings."""

from urllib.parse import unquote
from typing import List, Dict, Optional
import re
import requests
from bs4 import BeautifulSoup
from ..models import JobDetail, JobResult


class BeautifulSoupScraper:
    """Scraper using BeautifulSoup and requests for LinkedIn job data."""

    def __init__(self, timeout: int = 10):
        """
        Initialize the BeautifulSoup scraper.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def get_listings(
        self,
        job_title: str,
        location: str,
        pages: int = None,  # None means fetch all available pages
        time_filter: str = "r86400",  # last 24h
        experience_levels: str = "1,2,3"  # internship, entry, associate
    ) -> List[Dict[str, str]]:
        """
        Fetch job listing URLs and basic info from LinkedIn.
        
        Args:
            job_title: Job title/keywords to search
            location: Location to search in
            pages: Number of pages to fetch (25 results per page). 
                   If None, fetches all available pages.
            time_filter: Time filter (r86400=24h, r604800=week, r2592000=month)
            experience_levels: Comma-separated experience levels 
                (1=internship, 2=entry, 3=associate)
        
        Returns:
            List of dictionaries with keys: job_id, url, title, company, location
        """
        results: List[Dict[str, str]] = []
        page = 0
        max_pages = pages if pages is not None else float('inf')
        consecutive_empty_pages = 0
        max_consecutive_empty = 2  # Stop after 2 consecutive empty pages

        while page < max_pages:
            params = {
                "keywords": job_title,
                "location": location,
                "start": page * 25,
                "f_TPR": time_filter,
                "f_E": experience_levels,
            }

            try:
                resp = requests.get(
                    self.base_url,
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout
                )

                if resp.status_code != 200:
                    print(f"Failed to fetch page {page + 1}, status: {resp.status_code}")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("li")

                # Parse listings from this page
                page_results = []
                for card in cards:
                    listing = self._parse_listing_card(card)
                    if listing:
                        page_results.append(listing)

                # If no results found on this page
                if not page_results:
                    consecutive_empty_pages += 1
                    print(f"No job listings found on page {page + 1}")

                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"Reached end of available results at page {page + 1}")
                        break
                else:
                    consecutive_empty_pages = 0
                    results.extend(page_results)
                    print(f"Found {len(page_results)} listings on page {page + 1}")

                page += 1

            except requests.RequestException as e:
                print(f"Request error on page {page + 1}: {e}")
                break
            except Exception as e:
                print(f"Error processing page {page + 1}: {e}")
                page += 1  # Continue to next page on parsing errors
                continue

        print(f"Total listings fetched: {len(results)}")
        return results

    def _parse_listing_card(self, card) -> Optional[Dict[str, str]]:
        """
        Parse a single job listing card.
        
        Args:
            card: BeautifulSoup element for a job card
            
        Returns:
            Dictionary with job data or None if parsing fails
        """
        try:
            link_element = card.select_one("a.base-card__full-link")
            if not link_element:
                return None

            url = link_element["href"].split("?")[0]
            title = card.select_one("h3.base-search-card__title").get_text(strip=True)
            company = card.select_one("h4.base-search-card__subtitle").get_text(strip=True)
            location = card.select_one("span.job-search-card__location").get_text(strip=True)

            # Extract job ID from URL
            match = re.search(r"/jobs/view/(?:[\w-]+-)?(\d+)", url)
            job_id = match.group(1) if match else ""

            return {
                "job_id": job_id,
                "url": url,
                "title": title,
                "company": company,
                "location": location,
            }
        except (AttributeError, KeyError, TypeError):
            return None

    def fetch_details(self, listings: List[Dict[str, str]]) -> List[JobResult]:
        """
        Fetch detailed information for each job listing.
        
        Args:
            listings: List of job listings from get_listings()
            
        Returns:
            List of job dictionaries with full details added
        """
        results = []

        for listing in listings:
            url = listing.get("url")
            if not url:
                continue

            job_detail = self._fetch_job_detail(url)

            job_data = {
                **listing,
                "description": job_detail.description,
                "apply_url": job_detail.apply_url,
                "industry": job_detail.industry,
            }

            # Use detailed title/company if available and different
            if job_detail.title and job_detail.title != listing.get("title"):
                job_data["title"] = job_detail.title
            if job_detail.company and job_detail.company != listing.get("company"):
                job_data["company"] = job_detail.company

            job_result = JobResult(
                title=job_data.get("title"),
                company=job_data.get("company"),
                location=job_data.get("location"),
                description=job_data.get("description"),
                apply_url=job_data.get("apply_url"),
                industry=job_data.get("industry"),
                job_url="" if job_data.get("job_id") == "" \
                    else f"https://www.linkedin.com/jobs/view/{job_data.get('job_id')}"
            )
            results.append(job_result)

        return results

    def _fetch_job_detail(self, url: str) -> JobDetail:
        """
        Fetch detailed job information from a job detail page.
        
        Args:
            url: Job detail page URL
            
        Returns:
            Tuple of (description, apply_url, industry, title, company)
        """
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)

            # if resp.status_code != 200:
            #     return "", "", None, "", ""
            
            if resp.status_code != 200:
                return JobDetail()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract description
            desc_element = (
                soup.select_one(".show-more-less-html__markup")
                or soup.select_one(".description__text")
            )
            description = (
                desc_element.get_text(separator="\n", strip=True)
                if desc_element else ""
            )

            # Extract title and company
            title_element = (
                soup.select_one("h1.top-card-layout__title")
                or soup.select_one("h1")
            )
            title = title_element.get_text(strip=True) if title_element else ""

            company_element = (
                soup.select_one("span.topcard__flavor")
                or soup.select_one("a.topcard__org-name-link")
            )
            company = company_element.get_text(strip=True) if company_element else ""

            # Extract apply URL
            apply_url = self._extract_apply_url(soup)

            # Extract industry
            industry_element = soup.select_one(
                "li.jobs-unified-top-card__job-insight span[aria-hidden='true']"
            )
            industry = industry_element.get_text(strip=True) if industry_element else None

            return JobDetail(
                description=description,
                apply_url=apply_url,
                industry=industry,
                title=title,
                company=company)

        except requests.RequestException as e:
            print(f"Request error fetching details from {url}: {e}")
            return JobDetail()
        except Exception as e:
            print(f"Error parsing job details from {url}: {e}")
            return JobDetail()

    def _extract_apply_url(self, soup: BeautifulSoup) -> str:
        """
        Extract the application URL from the job detail page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Decoded apply URL or empty string
        """
        apply_url_content = soup.find("code", id="applyUrl")
        if not apply_url_content:
            return ""

        text = apply_url_content.decode_contents()
        if not isinstance(text, str):
            return ""

        match = re.search(r'(?<=\?url=)[^"]+', text)
        if match:
            return unquote(match.group())

        return ""
