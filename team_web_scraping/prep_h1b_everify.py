from job_scraper.utils.sponsor_prep import load_and_process, save_json
from job_scraper.config.settings import (
    H1B_COMPANY_COL, EVERIFY_COMPANY_COL,
    H1B_KEYS_JSON, EVERIFY_KEYS_JSON
)

def main(h1b_raw_path: str, csv_raw_path: str):
    h1b_keys = load_and_process(h1b_raw_path, H1B_COMPANY_COL)
    save_json(h1b_keys, H1B_KEYS_JSON)

    ev_keys = load_and_process(csv_raw_path, EVERIFY_COMPANY_COL)
    save_json(ev_keys, EVERIFY_KEYS_JSON)

if __name__ == "__main__":
    h1b_raw_path = "Employer Information.csv"
    csv_raw_path = "Employer List.csv"
    main(h1b_raw_path, csv_raw_path)
