from fastapi import FastAPI
from typing import List
from models import JobSearchRequest, JobResult
from listing import fetch_job_listing_urls
from scraper import SeleniumJobScraper

app = FastAPI(title="LinkedIn Job Scraper API (v3)")

@app.post("/scrape", response_model=List[JobResult])
def scrape_jobs(req: JobSearchRequest):
    job_entries = fetch_job_listing_urls(req.job_title, req.location, req.pages)
    scraper = SeleniumJobScraper(headless=True)
    try:
        results: list[JobResult] = []
        for idx, entry in enumerate(job_entries, 1):
            desc, apply_url, industry, title, company = scraper.fetch_detail(entry["url"])
            results.append(
                JobResult(
                    title=title or entry["title"],
                    company=company or entry["company"],
                    location=entry["location"],
                    description=desc,
                    apply_url=apply_url,
                    industry=industry,
                )
            )
            print(f"[{idx}/{len(job_entries)}] {title} | Apply: {apply_url}")
        print(f"✨ Finished. Total jobs fetched: {len(results)}")
        return results
    finally:
        scraper.close()          
