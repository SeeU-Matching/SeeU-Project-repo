from job_scraper.utils.save_csv import save_jobs_to_csv, load_jobs_from_csv
from job_scraper.core.sponsor_checker import SponsorChecker
import time

def main():
    local_output_file = "output\\jobs_batch_20260221_143342.csv"
    jobs = load_jobs_from_csv(local_output_file)
    print(len(jobs))
    start_time = time.time()
    sc = SponsorChecker()
    for job in jobs:
        result = sc.check(job.company)
        job.h1b_sponsored = "Yes" if result["h1b"] else "Unknown"
        job.e_verified = "Yes" if result["everify"] else "Unknown"
        # print(result)
    end_time = time.time()
    print(f"Processed h1b info completed in {end_time - start_time:.2f} seconds.")
    save_jobs_to_csv(jobs, local_output_file)

if __name__ == "__main__":
    main()