FROM python:3.13-slim

WORKDIR /app

# System deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY app/ ./app/
COPY .env.example .env

# Create workspace and logs dirs
RUN mkdir -p app/workspace app/logs

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.main"]
