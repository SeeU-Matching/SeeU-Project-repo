# quick_test.py
from job_scraper.core.selenium_scraper import SeleniumJobScraper
from dotenv import load_dotenv
load_dotenv()

url = "https://www.linkedin.com/jobs/view/bi-analyst-at-burberry-4239658831/?originalSubdomain=cn"
scraper = SeleniumJobScraper(headless=True)   # False so you can see what happens
try:
    job_result = scraper._fetch_job_detail(url)
    print("Title:      ", job_result.title)
    print("Company:    ", job_result.company)
    print("Industry:   ", job_result.industry)
    print("Apply link: ", job_result.apply_url)
    print("Description:", job_result.description[:300], "…")
finally:
    scraper.close()
