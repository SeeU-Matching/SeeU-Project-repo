from job_scraper.utils.keyword_loader import load_job_keywords

if __name__ == "__main__":
    KEYWORDS = load_job_keywords()
    for category, keywords in KEYWORDS.items():
        print(f"{category.name}: {keywords}")
