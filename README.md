# nano-ai

Autonomous AI agent running locally on Ollama. Lightweight, private, extensible.

## Features

- **Local LLM** — runs on Ollama, no cloud dependency
- **HTTP API** — FastAPI server with `/chat` endpoint
- **Stealth browser** — Playwright with anti-detection for web interaction
- **Workspace** — sandboxed file system for persistent storage
- **Code execution** — write and run Python, Bash, JavaScript
- **Context management** — sliding window to prevent overflow
- **Persistent memory** — remembers across sessions via workspace
- **Audit logs** — every action logged in JSONL

## Quick start

### Docker (one command)

```bash
docker compose up -d
```

That's it. Ollama starts, pulls `huihui_ai/qwen3.5-abliterated:4b` automatically, then the agent API is available at `http://localhost:8000`.

### API usage

```bash
# Chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'

# Reset conversation
curl -X POST http://localhost:8000/reset

# Health check
curl http://localhost:8000/health
```

### Local (without Docker)

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# API server
uvicorn app.server:app --host 0.0.0.0 --port 8000
# Or CLI mode
python -m app.main
```

## Architecture

```
app/
├── main.py              # CLI entry point
├── server.py            # HTTP API server
├── config.py            # Environment configuration
├── agent/               # Orchestration, context, display
├── llm/                 # Ollama API client
├── tools/               # Registry + workspace, browser, system tools
├── logger/              # Session audit logging
└── prompts/             # System prompt
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `API_MODEL` | `huihui_ai/qwen3.5-abliterated:4b` | Model to use |
| `API_CTX` | `4096` | Context window size |
| `API_TOKEN` | — | Auth token (optional) |

## Tools

| Tool | Description |
|------|-------------|
| `write_file` | Create/overwrite files in workspace |
| `read_file` | Read files |
| `list_files` | List workspace contents |
| `delete_file` | Delete files or directories |
| `run_file` | Execute .py, .sh, .js scripts |
| `get_date` | Current date and time |
| `web_search` | Search via DuckDuckGo |
| `web_read` | Read a page as markdown |
| `web_go` | Navigate and list interactive elements |
| `web_click` | Click page elements |
| `web_type` | Type into form fields |

## License

MIT
