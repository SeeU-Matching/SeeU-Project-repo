import os
from datetime import datetime
import logging
import boto3
from job_scraper import ConcurrentJobScraperService
from job_scraper.models.enums import States
from job_scraper.utils.keyword_loader import load_job_keywords

# Configure logging
logging.basicConfig(level=logging.WARN,\
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BatchJob")

def run_job():
    """Main running code"""

    # 1. Configuration & Secrets
    s3_bucket = os.environ.get("S3_BUCKET_NAME")
    s3_prefix = os.environ.get("S3_KEY_PREFIX", "scraped_jobs/")
    proxy_list_json = os.environ.get("PROXY_LIST_JSON")
    dry_run = os.environ.get("DRY_RUN", "False").lower() == "true"
    output_dir = os.getenv("OUTPUT_DIR", "/app/output")
    os.makedirs(output_dir, exist_ok=True)

    # Scraper config
    pages = None
    search_threads = int(os.environ.get("SEARCH_THREADS", "2"))
    detail_threads = int(os.environ.get("DETAIL_THREADS", "4"))

    # 2. Load Targets (Keywords & Locations)
    keywords_map = load_job_keywords()
    job_titles = []
    # flattened list of all keywords
    for _, kws in keywords_map.items():
        job_titles.extend(kws)

    # Optional: Limit job titles for testing if env var set
    if os.environ.get("LIMIT_KEYWORDS"):
        limit = int(os.environ.get("LIMIT_KEYWORDS"))
        job_titles = job_titles[:limit]
        logger.info("Limiting to first %s job titles.", limit)

    # Locations: Default to all States
    locations = [s.value for s in States]
    if os.environ.get("LIMIT_LOCATIONS"):
        limit_loc = int(os.environ.get("LIMIT_LOCATIONS"))
        locations = locations[:limit_loc]
        logger.info("Limiting to first %s locations.", limit_loc)

    logger.warning("Starting batch job used %s titles and %s locations.", \
                len(job_titles), len(locations))

    # 3. Run Scraper
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    local_output_file = os.path.join(
        output_dir,
        f"jobs_batch_{timestamp}.csv"
    )

    service = ConcurrentJobScraperService(timeout=15)

    try:
        service.scrape_and_export_batch(
            job_titles=job_titles,
            locations=locations,
            output_file=local_output_file,
            pages=pages,
            search_threads=search_threads,
            detail_threads=detail_threads,
            proxy_file=proxy_list_json
        )
    except KeyboardInterrupt:
        logger.warning("Batch job cancelled by user.")
        return
    except Exception as e:
        logger.error("Scraping failed: %s", e)
        raise

    # 4. Upload to S3
    if not dry_run and s3_bucket:
        s3_key = f"{s3_prefix}{local_output_file}"
        logger.warning("Uploading %s to s3://%s/%s", \
                    local_output_file, s3_bucket, s3_key)
        try:
            s3 = boto3.client("s3")
            s3.upload_file(local_output_file, s3_bucket, s3_key)
            logger.warning("Upload Successful.")
        except Exception as e:
            logger.error("Failed to upload to S3: %s", e)
            raise
    else:
        logger.warning("Dry run or no bucket specified. Output kept locally at %s", \
                       local_output_file)

if __name__ == "__main__":
    run_job()
