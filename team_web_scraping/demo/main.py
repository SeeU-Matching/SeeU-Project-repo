from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI
from ..job_scraper.service import JobScraperService
from ..job_scraper.models.job import JobResult, JobSearchRequest
import os
load_dotenv()

app = FastAPI(title="LinkedIn Job Scraper API")
scraper_service = JobScraperService(timeout=10)

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
