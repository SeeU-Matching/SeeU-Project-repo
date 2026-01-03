import requests
import os
from fastapi import FastAPI
from typing import List
from .models import JobSearchRequest, JobResult
from .listing import fetch_job_listing_urls, fetch_job_detail_bs
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="LinkedIn Job Scraper API (v3)")

@app.post("/scrape", response_model=List[JobResult])
def scrape_jobs(req: JobSearchRequest):
    job_entries = fetch_job_listing_urls(req.job_title, req.location, req.pages)
    # by default: use BeautifulSoup-only detail fetch. If `use_selenium` is True,
    # try to call an external Selenium service defined by SELENIUM_SERVICE_URL.
    selenium_service_url = os.environ.get("SELENIUM_SERVICE_URL", "http://localhost:8001/fetch_detail")
    if len(job_entries) > 5:
        job_entries = job_entries[:5]
    try:
        results: list[JobResult] = []
        for idx, entry in enumerate(job_entries, 1):
            if req.use_selenium:
                # call external Selenium detail service
                try:
                    resp = requests.post(selenium_service_url, json={"url": entry["url"]}, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json()
                        desc = data.get("description", "")
                        apply_url = data.get("apply_url", "")
                        industry = data.get("industry")
                        title = data.get("title", "")
                        company = data.get("company", "")
                    else:
                        # fallback to BeautifulSoup method
                        desc, apply_url, industry, title, company = fetch_job_detail_bs(entry["url"])
                except Exception:
                    desc, apply_url, industry, title, company = fetch_job_detail_bs(entry["url"])
            else:
                desc, apply_url, industry, title, company = fetch_job_detail_bs(entry["url"])
            results.append(
                JobResult(
                    title=title or entry["title"],
                    company=company or entry["company"],
                    location=entry["location"],
                    description=desc,
                    apply_url=apply_url,
                    industry=industry,
                    job_url="" if entry["job_id"] == "" else f"https://www.linkedin.com/jobs/view/{entry["job_id"]}"
                )
            )
            print(f"[{idx}/{len(job_entries)}] {title} | Apply: {apply_url}")
        print(f"✨ Finished. Total jobs fetched: {len(results)}")
        return results
    finally:
        # nothing to explicitly close in main pipeline when using external service
        pass
