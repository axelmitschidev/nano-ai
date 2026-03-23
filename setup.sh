#!/usr/bin/env bash
set -e

MODEL="huihui_ai/qwen3.5-abliterated:4b"

echo "=== nano-ai setup ==="

# 1. Check Ollama
if ! command -v ollama &>/dev/null; then
    echo ""
    echo "[!] Ollama is not installed."
    echo ""
    echo "  macOS:  brew install ollama"
    echo "  Linux:  curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    exit 1
fi

# 2. Start Ollama if not running
if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
    echo "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 2
fi

# 3. Pull model if missing
if ! ollama list 2>/dev/null | grep -q "qwen3.5-abliterated"; then
    echo "Pulling model ($MODEL)..."
    ollama pull "$MODEL"
fi

# 4. Python venv + deps
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing dependencies..."
.venv/bin/pip install -q -r requirements.txt

echo "Installing browser (Chromium)..."
.venv/bin/playwright install chromium 2>/dev/null

# 5. Config
if [ ! -f ".env" ]; then
    cp .env.example .env
fi

mkdir -p app/workspace app/logs

echo ""
echo "=== Ready ==="
echo ""
echo "  .venv/bin/python -m app.main"
echo ""
