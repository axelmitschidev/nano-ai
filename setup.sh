#!/usr/bin/env bash
set -e

echo "=== nano-ai setup ==="

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing dependencies..."
.venv/bin/pip install -q -r requirements.txt

echo "Installing browser (Chromium)..."
.venv/bin/playwright install chromium 2>/dev/null

# Create .env if missing
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

# Create workspace/logs dirs
mkdir -p app/workspace app/logs

echo ""
echo "=== Ready ==="
echo ""
echo "  CLI mode:  .venv/bin/python -m app.main"
echo "  API mode:  .venv/bin/uvicorn app.server:app --host 0.0.0.0 --port 8000"
echo ""
echo "  Make sure Ollama is running: ollama serve"
echo ""
