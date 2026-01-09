import csv
from typing import List

from job_scraper.models.job import JobResult

def save_jobs_to_csv(jobs: List[JobResult], file_path: str ="jobs.csv"):
    """
        Util function to save jobResults into csv
    """
    if not jobs:
        return

    fieldnames = [
        "title",
        "company",
        "location",
        "description",
        "job_url",
        "apply_url",
        "industry",
    ]

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for job in jobs:
            writer.writerow(job.model_dump())
