from urllib.parse import unquote
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

                m = re.search(r"/jobs/view/(?:[\w-]+-)?(\d+)", url)
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


def fetch_job_detail_bs(url: str, timeout: int = 10) -> tuple[str, str, str | None, str, str]:
    """Best-effort fetch of job detail using requests + BeautifulSoup.
    Returns: description, apply_url, industry, title, company
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return "", "", None, "", ""
        soup = BeautifulSoup(resp.text, "html.parser")

        # description
        desc_el = soup.select_one(".show-more-less-html__markup") or soup.select_one(".description__text")
        description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

        # title / company
        title_el = soup.select_one("h1.top-card-layout__title") or soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        company_el = soup.select_one("span.topcard__flavor") or soup.select_one("a.topcard__org-name-link")
        company = company_el.get_text(strip=True) if company_el else ""

        # apply url
        apply_url = ""
        apply_url_regex = re.compile(r'(?<=\?url=)[^"]+')
        apply_url_content = soup.find("code", id="applyUrl")
        if apply_url_content:
            apply_url_match = apply_url_regex.search(
                apply_url_content.decode_contents().strip()
            )
            if apply_url_match:
                apply_url = unquote(apply_url_match.group())

        industry_el = soup.select_one("li.jobs-unified-top-card__job-insight span[aria-hidden='true']")
        industry = industry_el.get_text(strip=True) if industry_el else None

        return description, apply_url, industry, title, company
    except Exception:
        return "", "", None, "", ""