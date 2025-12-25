from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import os

class SeleniumJobScraper:
    def __init__(self, headless: bool = True):
        chromedriver_path = "/Users/christang/Desktop/jd_fetching/chromedriver"
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")

        # ✅ Use dedicated Chrome user data directory to avoid conflict
        opts.add_argument("--user-data-dir=/Users/christang/Desktop/jd_fetching/chrome_user_data")

        self.driver = webdriver.Chrome(service=Service(chromedriver_path), options=opts)

    def fetch_detail(
        self, url: str, timeout: int = 12
    ) -> tuple[str, str, str | None, str, str]:
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

        # ❶  ONLY the absolute XPath you trust
        APPLY_LOCATOR = (
            By.XPATH,
            "/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/"
            "div/div/div/div[6]/div/div/div/button",
        )

        try:
            btn = WebDriverWait(d, timeout).until(
                EC.element_to_be_clickable(APPLY_LOCATOR)
            )
            original_window = d.current_window_handle
            original_url    = d.current_url
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

        return description, apply_link, industry, title, company


    def close(self):
        self.driver.quit()
