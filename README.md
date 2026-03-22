# nano-ai

Autonomous AI agent running locally on Ollama. Lightweight, private, extensible.

## Features

- **Local LLM** — runs on Ollama, no cloud dependency
- **Stealth browser** — Playwright with anti-detection for web interaction
- **Workspace** — sandboxed file system for persistent storage
- **Code execution** — write and run Python, Bash, JavaScript
- **Context management** — sliding window to prevent overflow
- **Persistent memory** — remembers across sessions via workspace
- **Audit logs** — every action logged in JSONL

## Architecture

```
app/
├── main.py              # Entry point
├── config.py            # Environment configuration
├── agent/               # Orchestration, context, display
├── llm/                 # Ollama API client
├── tools/               # Registry + workspace, browser, system tools
├── logger/              # Session audit logging
└── prompts/             # System prompt
```

## Quick start

### Local

```bash
# Prerequisites: Python 3.13+, Ollama running locally
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # edit model/ctx as needed
python -m app.main
```

### Docker

```bash
docker compose up -d
# Pull a model inside the Ollama container
docker exec nano-ollama ollama pull qwen3.5:4b
# Attach to the agent
docker attach nano-agent
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `API_MODEL` | `qwen3.5:4b` | Model to use |
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
