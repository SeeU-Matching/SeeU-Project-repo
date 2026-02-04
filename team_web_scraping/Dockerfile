FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if any (e.g. for lxml or other libs)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libxml2-dev libxslt-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
# We copy job_scraper directory to /app/job_scraper
COPY job_scraper/ ./job_scraper/
COPY run_batch_job.py .

# Ensure PYTHONPATH includes the current directory so imports work
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "run_batch_job.py"]
