<p align="center">
  <h1 align="center">nano-ai</h1>
  <p align="center"><strong>Your own AI agent. Local. Private. Autonomous.</strong></p>
  <p align="center">One command. No cloud. No API key. No limits.</p>
</p>

<p align="center">
  <a href="https://github.com/axelmitschidev/nano-ai/stargazers"><img src="https://img.shields.io/github/stars/axelmitschidev/nano-ai?style=social" alt="Stars"></a>
  <a href="https://github.com/axelmitschidev/nano-ai/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/model-4B%20params-green.svg" alt="Model">
  <img src="https://img.shields.io/badge/runs%20on-your%20machine-black.svg" alt="Local">
</p>

---

> An autonomous AI agent that runs entirely on your machine. It browses the web, writes and executes code, manages files, and remembers across sessions — all with a 4B parameter model. No cloud. No telemetry. Just you and your agent.

---

## What can it do?

- **Browse the web** — stealth browser that bypasses bot detection. Search, read pages, fill forms, click buttons
- **Write and run code** — creates Python/Bash/JS scripts and executes them autonomously
- **Manage files** — sandboxed workspace for persistent storage and memory
- **Remember** — persistent memory across sessions, learns and adapts
- **Think** — chain-of-thought reasoning visible in real-time
- **Use tools autonomously** — picks the right tool, handles errors, retries, adapts

All of this running locally on a **4B parameter model**. On a laptop. In a Docker container.

---

## Get started in 30 seconds

```bash
git clone https://github.com/axelmitschidev/nano-ai.git
cd nano-ai
docker compose up -d
```

That's it. Ollama starts, pulls the model, and the agent API is live at `http://localhost:8000`.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "search the web for the latest AI news and save a summary"}'
```

The agent will search the web, read articles, write a summary, and save it to its workspace. Autonomously.

---

## How it works

```
User message
    |
    v
[Agent Loop] ──> thinks (chain-of-thought)
    |                |
    |                v
    |         picks a tool
    |                |
    |    ┌───────────┼───────────┐
    |    v           v           v
  [Files]      [Browser]     [Code]
  read/write   search/click  run .py/.sh/.js
    |           navigate
    |           fill forms
    |                |
    └────────────────┘
    |
    v
 Response (or call another tool)
```

The agent loops until the task is done. It handles errors, retries failed operations, and adapts its approach when something doesn't work.

---

## Architecture

```
app/
├── main.py              # CLI entry point
├── server.py            # HTTP API (FastAPI)
├── config.py            # Configuration
├── agent/               # Core agent loop, context management, display
├── llm/                 # Ollama client
├── tools/               # Tool registry + implementations
│   ├── workspace.py     # File operations (sandboxed)
│   ├── browser.py       # Stealth web browser
│   └── system.py        # Code execution, date
├── logger/              # JSONL audit logs
└── prompts/             # System prompt
```

Clean architecture. SOLID principles. Every tool is a module — add your own in minutes.

---

## API

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/chat` | `{"message": "..."}` → `{"response": "..."}` |
| `POST` | `/reset` | Reset conversation |
| `GET` | `/health` | Status check |
| `GET` | `/docs` | Swagger UI |

---

## Tools

| Tool | What it does |
|------|-------------|
| `write_file` | Create/overwrite files in workspace |
| `read_file` | Read files |
| `list_files` | List workspace contents |
| `delete_file` | Delete files or directories |
| `run_file` | Execute .py, .sh, .js scripts |
| `get_date` | Current date and time |
| `web_search` | Search via DuckDuckGo |
| `web_read` | Read a page as clean markdown |
| `web_go` | Navigate and list interactive elements |
| `web_click` | Click buttons, links |
| `web_type` | Type into form fields |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `API_MODEL` | `huihui_ai/qwen3.5-abliterated:4b` | Model |
| `API_CTX` | `65536` | Context window |

---

## Run without Docker

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env

# API mode
uvicorn app.server:app --port 8000

# CLI mode
python -m app.main
```

---

## Why nano-ai?

| | nano-ai | Cloud agents | Other local agents |
|---|---------|-------------|-------------------|
| **Privacy** | 100% local | Your data on their servers | Varies |
| **Cost** | Free forever | $20-200/month | Free |
| **Setup** | 1 command | Account + API key | Complex |
| **Internet** | Stealth browser | Limited/none | Usually none |
| **Code exec** | Yes, sandboxed | Restricted | Rare |
| **Size** | 4B params, ~3GB | 200B+ params | 7-70B |
| **Works offline** | Yes (except web tools) | No | Yes |

---

## Contributing

PRs welcome. The tool registry is designed to be extended — add a new tool in one file, register it, done.

---

## License

MIT
