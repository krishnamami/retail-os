FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (minimal for asyncpg + boto3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ingest_s3_to_postgres.py .

# Run (ECS task will invoke via CMD)
CMD ["python", "ingest_s3_to_postgres.py"]
