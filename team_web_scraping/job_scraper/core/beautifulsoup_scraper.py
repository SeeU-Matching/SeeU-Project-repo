"""BeautifulSoup-based scraper for LinkedIn job listings."""
import logging
import time
from urllib.parse import unquote
from typing import List, Dict, Optional, Any
import re
import requests
from bs4 import BeautifulSoup
from job_scraper.models import JobDetail, JobResult
from job_scraper.models.enums import States
from job_scraper.utils import create_session, human_delay

logger = logging.getLogger(__name__)


class ProxyRateLimitError(Exception):
    """Raised when a 429 status code is received."""
    pass


class BeautifulSoupScraper:
    """Scraper using BeautifulSoup and requests for LinkedIn job data."""
    def __init__(
        self,
        timeout: int = 10,
        proxies: Optional[Dict[str, str]] = None,
        job_id_cache: Optional[set] = None,
        job_id_lock: Optional[Any] = None
    ):
        """
        Initialize the BeautifulSoup scraper.
        
        Args:
            timeout: Request timeout in seconds
            proxies: Dictionary of proxies to use
            job_id_cache: Optional shared set for job IDs across threads
            job_id_lock: Optional shared lock for thread-safe cache access
        """
        self.timeout = timeout
        self.session = create_session()
        if proxies:
            self.session.proxies.update(proxies)
        self.base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        self.job_id_cache = job_id_cache if job_id_cache is not None else set()
        self.job_id_lock = job_id_lock

    def clear_cache(self):
        """Clear the job ID cache to avoid infinite growth."""
        self.job_id_cache.clear()

    def get_listings(
        self,
        job_title: str,
        location: str,
        pages: int = None,  # None means fetch all available pages
        time_filter: str = "r86400",  # last 24h
        experience_levels: str = "1,2,3",  # internship, entry, associate
        enforce_united_states: bool = False
    ) -> List[Dict[str, str]]:
        """
        Fetch job listing URLs and basic info from LinkedIn.
        
        Args:
            job_title: Job title/keywords to search
            location: Location to search in
            pages: Number of pages to fetch (10 results per page). 
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

        while page < max_pages:
            search_location = location
            if enforce_united_states and "United States" not in search_location:
                search_location += ", United States"

            params = {
                "keywords": job_title,
                "location": search_location,
                "start": page * 10,
                "f_TPR": time_filter,
                "f_E": experience_levels,
            }

            try:
                resp_start = time.time()
                resp = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout
                )
                logger.debug("Request time %s", time.time() - resp_start)

                if resp.status_code == 429:
                    logger.warning("Rate limit exceeded (429) on page %s", page + 1)
                    raise ProxyRateLimitError("Rate limit exceeded")

                if resp.status_code != 200:
                    logger.warning("Failed to fetch page %s, \
                                   status: %s", page + 1, resp.status_code)
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("li")

                # Parse listings from this page
                page_results = []
                logger.debug("%s cards found", len(cards))
                for card in cards:
                    parse_start = time.time()
                    listing = self._parse_listing_card(card)
                    logger.debug("Card parsing time %s", time.time() - parse_start)
                    if listing:
                        job_id = listing.get("job_id")
                        if job_id:
                            # Thread-safe check and add
                            is_duplicate = False
                            if self.job_id_lock:
                                with self.job_id_lock:
                                    if job_id in self.job_id_cache:
                                        is_duplicate = True
                                    else:
                                        self.job_id_cache.add(job_id)
                            else:
                                # Fallback for single-threaded usage without lock being explicitly passed
                                # (though ideally one should verify if single-threaded needs lock)
                                if job_id in self.job_id_cache:
                                    is_duplicate = True
                                else:
                                    self.job_id_cache.add(job_id)

                                if is_duplicate:
                                    logger.debug("Duplicate job found, skipping: %s", job_id)
                                    continue

                        if enforce_united_states:
                            loc_text = listing.get("location", "")
                            if not self._is_us_location(loc_text):
                                logger.debug("Skipping non-US location: %s", loc_text)
                                continue

                        page_results.append(listing)

                if len(page_results) > 0:
                    results.extend(page_results)
                    logger.debug("Found %s listings on page %s", len(page_results), page + 1)

                if len(cards) < 10:
                    logger.debug("Page %s had fewer than 10 results (%s), \
                                 indicating last page, stopping.", page + 1, len(page_results))
                    break

                page += 1
                human_delay(2, 5)

            except requests.RequestException as e:
                logger.error("Request error on page %s: %s", page + 1, e)
                break
            except ProxyRateLimitError:
                raise  # Re-raise to be handled by caller
            except Exception as e:
                logger.error("Error processing page %s: %s", page + 1, e)
                page += 1  # Continue to next page on parsing errors
                continue

        logger.debug("Total listings fetched: %s", len(results))
        return results

    def _is_us_location(self, location: str) -> bool:
        """
        Check if the location string is likely within the US.
        From observation, correct location is either like "Idaho, United States"
        or "Huntsville, AL"
        
        Args:
            location: Location string from LinkedIn (e.g. "New York, NY", "Berlin, Germany")
            
        Returns:
            True if it looks like a US location, False otherwise
        """
        if not location:
            return False

        # 1. Check for explicit "United States"
        if "United States" in location:
            return True

        # 2. Check for state abbreviations at the end
        parts = [p.strip() for p in location.split(",")]

        if not parts:
            return False

        last_part = parts[-1]

        # Check against known US state codes
        if len(last_part) == 2 and last_part.upper() in [s.value for s in States]:
            return True

        if len(parts) >= 3:
            # If 3 parts, the last part MUST be United States literally, which we caught in check #1.
            # So if we are here (not caught by #1), and have 3 parts, it's likely foreign.
            return False

        if len(parts) == 2:
            if len(last_part) == 2:
                # We already checked state codes above. If it was a state code, it returned True.
                # So here it is a 2-letter code that is NOT a US state (e.g. "UK"?).
                pass
            else:
                pass

        return True

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
            match = re.search(r"/jobs/view/.*?(\d+)", url)
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
            
            detail_start = time.time()
            job_detail = self._fetch_job_detail(url)
            logger.debug("Fetch detail time %s", time.time() - detail_start)

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
            human_delay(1, 3)

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
            resp = self.session.get(url, timeout=self.timeout)

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
            logger.error("Request error fetching details from %s: %s", url, e)
            return JobDetail()
        except Exception as e:
            logger.error("Error parsing job details from %s: %s", url, e)
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
