# Job Scraping

This project provides a job scraping service with both:

- A **FastAPI server** (HTTP API)
- **Standalone Python scripts** for quick testing and basic usage

It supports optional Selenium-based scraping when enabled.

---

## Environment Setup

### 1. Create Conda Environment

Create and activate the Conda environment using the provided `env.yaml`:

```bash
conda env create -f env.yaml
conda activate JobInfoCrawling
```
### 2. Create .env in project root
```bash
SELENIUM_CHROMEDRIVER_PATH=/absolute/path/to/chromedriver
SELENIUM_USER_DATA_DIR=/absolute/path/to/chrome/user/data
```

## Running Server
```bash
cd team_web_scraping
uvicorn team_web_scraping.demo.main:app --reload --host 127.0.0.1 --port 8000
```
### Endpoint
```bash
POST /scrape
```
```bash
http://localhost:8000/scrape
```
### Request Body
```bash
{
  "job_title": "software engineer",
  "location": "united states",
  "pages": 1,
  "use_selenium": false
}
```

### Example Scripts
Run in project root
```bash
cd team_web_scraping
python -m examples.basic_usage
```
```bash
cd team_web_scraping
python -m examples.quick_testing
```

## install job_scraper as dependency(other teams)
```bash
cd team_web_scraping
pip install -e .
```
