# quick_test.py
from scraper import SeleniumJobScraper

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
