from job_scraper.core.beautifulsoup_scraper import BeautifulSoupScraper
from job_scraper.models.enums import States
from job_scraper.utils.keyword_loader import load_job_keywords


def test():
    KEYWORDS = load_job_keywords()
    job_titles = []
    for _, keywords in KEYWORDS.items():
        job_titles.extend(keywords)

    bf_scraper = BeautifulSoupScraper()
    total_count = 0

    for state in States:
        state_count = 0
        for job_title in job_titles:
            results = bf_scraper.get_listings(job_title=job_title, location=state.value)
            print(f"State {state.value} has {len(results)} jobs for {job_title}")
            state_count += len(results)
        print(f"Total of {state_count} jobs for {state.value}")
        total_count += state_count

    print(f"Total of {total_count} jobs")

if __name__ == "__main__":
    test()
