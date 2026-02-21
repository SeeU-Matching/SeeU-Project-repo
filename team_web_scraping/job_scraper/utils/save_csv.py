import csv
from typing import List

from job_scraper.models.job import JobResult

def save_jobs_to_csv(jobs: List[JobResult], file_path: str ="jobs.csv", mode: str = "w", write_header: bool = True):
    """
        Util function to save jobResults into csv
    """
    fieldnames = list(JobResult.model_fields.keys())

    with open(file_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        if jobs:
            for job in jobs:
                writer.writerow(job.model_dump())

def load_jobs_from_csv(file_path: str) -> List[JobResult]:
    jobs = []

    with open(file_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Convert empty strings back to None
            cleaned_row = {
                key: (value if value != "" else None)
                for key, value in row.items()
            }

            job = JobResult.model_validate(cleaned_row)
            jobs.append(job)

    return jobs