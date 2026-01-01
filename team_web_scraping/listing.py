import datetime
import requests
from bs4 import BeautifulSoup
import re

def fetch_job_listing_urls(job_title: str, location: str, pages: int = 1) -> list[dict]:
    """Return a list of dictionaries with keys:
    job_id, url, title, company, location

    Uses LinkedIn public guest endpoint so no login is needed.
    """

    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    results: list[dict] = []

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }

    for page in range(pages):
        params = {
            "keywords": job_title,
            "location": location,
            "start": page * 25,
            "f_TPR": "r86400",  # last 24h filter
            "f_E": "1,2,3",  # experience levels: internship, entry, associate
        }

        resp = requests.get(base_url, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("li")
        if not cards:
            break

        for card in cards:
            try:
                url = card.select_one("a.base-card__full-link")[
                    "href"
                ].split("?")[0]
                title = card.select_one("h3.base-search-card__title").get_text(strip=True)
                company = card.select_one("h4.base-search-card__subtitle").get_text(strip=True)
                loc = card.select_one("span.job-search-card__location").get_text(strip=True)

                m = re.search(r"/jobs/view/(\d+)", url)
                job_id = m.group(1) if m else ""

                results.append(
                    {
                        "job_id": job_id,
                        "url": url,
                        "title": title,
                        "company": company,
                        "location": loc,
                    }
                )
            except Exception:
                continue

    return results
