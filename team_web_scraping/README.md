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

## Running with Docker

### Prerequisites
- Docker installed
- `proxies.json` file in the directory(team_web_scraping)

### Using Docker Compose
1. Build and run:
```bash
docker-compose up --build
```
Outputs will be saved to `./output`.

To automatically stop when the scraper finishes:
```bash
docker-compose up --build --abort-on-container-exit
```

### Manual Build & Run
1. Build image:
```bash
docker build -t seeu-scraper .
```

2. Run container:
```bash
# Linux/Mac
docker run --rm \
  -v $(pwd)/proxies.json:/app/proxies.json \
  -v $(pwd)/output:/app/output \
  -e PROXY_LIST_JSON=/app/proxies.json \
  -e OUTPUT_DIR=/app/output \
  seeu-scraper

# Windows (CMD)
docker run --rm ^
  -v %cd%/proxies.json:/app/proxies.json ^
  -v %cd%/output:/app/output ^
  -e PROXY_LIST_JSON=/app/proxies.json ^
  -e OUTPUT_DIR=/app/output ^
  seeu-scraper
```

## install job_scraper as dependency(other teams)
```bash
cd team_web_scraping
pip install -e .
```
