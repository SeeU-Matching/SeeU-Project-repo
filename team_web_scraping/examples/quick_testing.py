# quick_test.py
from team_web_scraping.job_scraper.core.selenium_scraper import SeleniumJobScraper
from dotenv import load_dotenv
load_dotenv()

url = "https://www.linkedin.com/jobs/view/bi-analyst-at-burberry-4239658831/?originalSubdomain=cn"
scraper = SeleniumJobScraper(headless=True)   # False so you can see what happens
try:
    desc, apply_url, industry, title, company = scraper.fetch_detail(url)
    print("Title:      ", title)
    print("Company:    ", company)
    print("Industry:   ", industry)
    print("Apply link: ", apply_url)
    print("Description:", desc[:300], "…")
finally:
    scraper.close()
