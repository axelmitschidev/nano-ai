FROM python:3.13-slim

WORKDIR /app

# System deps (cached layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps (cached layer - only rebuilds when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright (cached layer - only rebuilds when requirements.txt changes)
RUN playwright install --with-deps chromium

# App code (changes frequently - last layer)
COPY app/ ./app/
RUN mkdir -p app/workspace app/logs

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
