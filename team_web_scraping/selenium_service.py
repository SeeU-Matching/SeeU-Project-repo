from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
load_dotenv()

from .scraper import SeleniumJobScraper


class FetchRequest(BaseModel):
    url: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    

    # ---------- Startup ----------
    chromedriver = os.environ.get("SELENIUM_CHROMEDRIVER_PATH")
    user_data = os.environ.get("SELENIUM_USER_DATA_DIR")

    if not chromedriver:
        raise RuntimeError(
            "SELENIUM_CHROMEDRIVER_PATH must be set to start selenium_service"
        )

    app.state.scraper = SeleniumJobScraper(
        headless=True,
        chromedriver_path=chromedriver,
        user_data_dir=user_data,
    )

    yield

    # ---------- Shutdown ----------
    scraper: Optional[SeleniumJobScraper] = getattr(app.state, "scraper", None)
    if scraper:
        try:
            scraper.close()
        except Exception:
            pass


app = FastAPI(
    title="Selenium Job Detail Service",
    lifespan=lifespan,
)


@app.post("/fetch_detail")
def fetch_detail(req: FetchRequest, request: Request):
    scraper: SeleniumJobScraper = request.app.state.scraper

    desc, apply_url, industry, title, company = scraper.fetch_detail(req.url)

    return {
        "description": desc,
        "apply_url": apply_url,
        "industry": industry,
        "title": title,
        "company": company,
    }
