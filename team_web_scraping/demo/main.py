from typing import List
import os
import csv
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from team_web_scraping.job_scraper.utils.save_csv import save_jobs_to_csv
from ..job_scraper.service import JobScraperService
from ..job_scraper.models import JobResult, JobSearchRequest, JobCSVSearchRequest

load_dotenv()

app = FastAPI(title="LinkedIn Job Scraper API")
scraper_service = JobScraperService(timeout=10)

BASE_DIR = Path(__file__).resolve().parent.parent
JOB_TITLES_CSV = BASE_DIR / "job_titles.csv"
OUTPUT_PATH = BASE_DIR / "all_jobs.csv"

@app.post("/scrape", response_model=List[JobResult])
def scrape_jobs(req: JobSearchRequest):
    """ 
        by default: use BeautifulSoup-only detail fetch. If `use_selenium` is True,
        try to call an external Selenium service defined by SELENIUM_SERVICE_URL.
    """
    print(os.environ.get("SELENIUM_CHROMEDRIVER_PATH"))
    results = scraper_service.scrape_jobs(req.job_title,
                                          req.location,
                                          req.pages,
                                          req.use_selenium)
    return results


@app.post("/scrape/from-csv", response_model=List[JobResult])
def scrape_from_csv(req: JobCSVSearchRequest):
    """
    Read job_titles.csv and scrape each title sequentially.
    Returns ALL jobs in one list.
    """
    if not JOB_TITLES_CSV.exists():
        raise HTTPException(status_code=404, detail="job_titles.csv not found")

    all_results: List[JobResult] = []

    with JOB_TITLES_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            title = (row.get("Job Title") or "").strip()
            print(title)
            if not title:
                continue

            jobs = scraper_service.scrape_jobs(
                job_title=title,
                location=req.location,
                pages=req.pages,
                use_selenium_for_details=req.use_selenium,
            )
            all_results.extend(jobs)
            save_jobs_to_csv(jobs, OUTPUT_PATH)

    return all_results