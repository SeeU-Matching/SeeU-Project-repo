import time
import os
import atexit
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from ..models import JobDetail, JobResult

class SeleniumJobScraper:
    def __init__(self,
                 headless: bool = True,
                 chromedriver_path: str | None = None,
                 user_data_dir: str | None = None):
        # Allow overriding via args or environment variables
        chromedriver_path = chromedriver_path or os.environ.get("SELENIUM_CHROMEDRIVER_PATH")
        user_data_dir = user_data_dir or os.environ.get("SELENIUM_USER_DATA_DIR")

        if not chromedriver_path:
            raise ValueError("chromedriver_path must be provided either \
                              as arg or in SELENIUM_CHROMEDRIVER_PATH")

        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")

        if user_data_dir:
            opts.add_argument(fr"--user-data-dir={user_data_dir}")

        self.driver = webdriver.Chrome(service=Service(chromedriver_path), options=opts)

        # Ensure driver quits on process exit to avoid orphaned browsers
        atexit.register(self._atexit_quit)

    def _atexit_quit(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

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

    def _fetch_job_detail(
        self, url: str, timeout: int = 5
    ) -> JobDetail:
        d = self.driver
        d.get(url)
        print(">>> Navigated to:", url)
        time.sleep(1)

        # ───────────────────────── description ─────────────────────────
        try:
            see_more = WebDriverWait(d, timeout).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    # works for both condensed & expanded layouts
                    "//button[@aria-label='Click to see more description' or "
                    "contains(@class,'jobs-description__footer-button')]"
                ))
            )
            d.execute_script("arguments[0].click();", see_more)
        except TimeoutException:
            pass

        try:
            WebDriverWait(d, timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "show-more-less-html__markup"))
            )
            description = d.find_element(
                By.CLASS_NAME, "show-more-less-html__markup"
            ).text.strip()
        except Exception:
            description = ""

        # ──────────────────────── title / company ──────────────────────
        title = (
            d.find_element(By.CSS_SELECTOR, "h1.top-card-layout__title").text.strip()
            if d.find_elements(By.CSS_SELECTOR, "h1.top-card-layout__title")
            else ""
        )
        company = (
            d.find_element(By.CSS_SELECTOR, "span.topcard__flavor").text.strip()
            if d.find_elements(By.CSS_SELECTOR, "span.topcard__flavor")
            else ""
        )

        # ───────────────────────── apply URL ───────────────────────────
        apply_link = ""

        # capture original window/url for fallbacks
        original_window = d.current_window_handle
        original_url = d.current_url

        # ❶  ONLY the absolute XPath you trust
        APPLY_LOCATOR = (
            By.XPATH,
            "/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/"
            "div/div/div/div[6]/div/div/div/button",
            # "/html/body/main/section[1]/div/section[2]/div/div[1]/div/div/button",
        )

        try:
            btn = WebDriverWait(d, timeout).until(
                EC.element_to_be_clickable(APPLY_LOCATOR)
            )
            d.execute_script("arguments[0].click();", btn)
            time.sleep(2)

            # 1️⃣ New window/tab?
            new_tabs = [w for w in d.window_handles if w != original_window]
            if new_tabs:
                d.switch_to.window(new_tabs[0])
                apply_link = d.current_url
                d.close()
                d.switch_to.window(original_window)
            else:
                # 2️⃣ Same-tab redirect?
                if d.current_url != original_url:
                    apply_link = d.current_url
                else:
                    if d.find_elements(
                        By.CSS_SELECTOR,
                        "div.jobs-easy-apply-modal, div[role='dialog'][data-test-modal='easy-apply']",
                    ):
                        apply_link = "Easy Apply (modal)"
                    else:
                        apply_link = ""

        except Exception as e:
            ts   = int(time.time())
            shot = f"apply_button_fail_{ts}.png"
            d.save_screenshot(shot)
            print(f"⚠️  Could not fetch apply URL: {e} – screenshot {shot}")

        # ───────────────────────── industry (optional) ─────────────────
        try:
            industry = d.find_element(
                By.CSS_SELECTOR,
                "li.jobs-unified-top-card__job-insight span[aria-hidden='true']",
            ).text.strip()
        except Exception:
            industry = None

        return JobDetail(
            description=description,
            apply_url=apply_link,
            industry=industry,
            title=title,
            company=company
        )

    def close(self):
        self.driver.quit()
