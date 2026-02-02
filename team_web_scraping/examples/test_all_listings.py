import logging
from job_scraper.core.beautifulsoup_scraper import BeautifulSoupScraper
from job_scraper.models.enums import States
from job_scraper.utils.keyword_loader import load_job_keywords
from job_scraper.utils.http import human_delay

logging.basicConfig(level=logging.DEBUG)

def test():
    KEYWORDS = load_job_keywords()
    job_titles = []
    for _, keywords in KEYWORDS.items():
        job_titles.extend(keywords)

    job_titles = job_titles[:1]

    bf_scraper = BeautifulSoupScraper()
    total_count = 0

    for state in States:
        state_count = 0
        for job_title in job_titles:
            results = bf_scraper.get_listings(job_title=job_title, location=state.value, enforce_united_states=True)
            for result in results:
                print("location: ", result.get("location", ""))
            print(f"State {state.value} has {len(results)} jobs for {job_title}")
            state_count += len(results)
            human_delay(2, 4)
        print(f"Total of {state_count} jobs for {state.value}")
        total_count += state_count

    print(f"Total of {total_count} jobs")

if __name__ == "__main__":
    test()
