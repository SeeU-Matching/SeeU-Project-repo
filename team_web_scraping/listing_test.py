from listing import fetch_job_listing_urls

jobs = fetch_job_listing_urls(
    job_title="business solutions analyst",
    location="United States",
    pages=1,
)

print(f"Found {len(jobs)} jobs")
for j in jobs[:5]:
    print(j["title"], "|", j["company"], "|", j["location"], "|", j["url"])