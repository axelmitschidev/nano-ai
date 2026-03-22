<p align="center">
  <img src="assets/banner.png" alt="nano-ai" width="600">
</p>
<p align="center"><strong>Your own AI agent. Local. Private. Autonomous.</strong></p>
<p align="center">One command. No cloud. No API key. No limits.</p>

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
- **Use tools autonomously** — picks the right tool, handles errors, retries, detects loops

All of this running locally on a **4B parameter model**. On a laptop.

---

## Get started

### Mac (recommended — uses Metal GPU acceleration)

1. Install Ollama natively:
```bash
brew install ollama
ollama pull huihui_ai/qwen3.5-abliterated:4b
```

2. Start the agent:
```bash
git clone https://github.com/axelmitschidev/nano-ai.git
cd nano-ai
docker compose --profile mac up -d --build
```

### Linux / CI (Ollama runs in Docker)

```bash
git clone https://github.com/axelmitschidev/nano-ai.git
cd nano-ai
docker compose --profile linux up -d --build
```

The agent API is live at `http://localhost:8000`.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "search the web for the latest AI news and save a summary"}'
```

---

## How it works

```
User message
    |
    v
[Agent Orchestrator]  (async)
    |
    ├──> picks a tool
    |        |
    |    ┌───┼──────────┐
    |    v   v          v
    |  [Files]  [Browser]  [Code]
    |    |        |          |
    |    └────────┘──────────┘
    |        |
    |    tool result
    |        |
    ├──> picks another tool (if needed)
    |        ...
    v
 Response
```

The agent loops until the task is done. It handles errors, retries failed operations, detects infinite loops, and manages its own context window.

### Built-in safety

- **Sandboxed workspace** — file operations restricted to the workspace directory
- **Execution timeout** — scripts are killed after 30 seconds
- **Context management** — sliding window prevents memory overflow
- **Loop detection** — breaks out of repeated tool calls
- **Retry with backoff** — web tools retry up to 3 times on failure
- **Session cap** — max 100 concurrent sessions with automatic eviction

---

## API

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/chat` | `{"message": "...", "session_id": "..."}` → `{"response": "...", "session_id": "..."}` |
| `POST` | `/reset` | Reset a conversation session |
| `GET` | `/health` | Status check (agent + Ollama) |
| `GET` | `/docs` | Interactive Swagger UI |

### Sessions

Each conversation gets a `session_id`. Pass it in subsequent requests to continue the conversation. Sessions expire after 1 hour of inactivity.

```bash
# Start a new conversation
curl -X POST http://localhost:8000/chat \
  -d '{"message": "hello"}'
# {"response": "Hi!", "session_id": "abc-123"}

# Continue the conversation
curl -X POST http://localhost:8000/chat \
  -d '{"message": "what did I just say?", "session_id": "abc-123"}'
# {"response": "You said hello.", "session_id": "abc-123"}
```

---

## Architecture

```
app/
├── main.py              # CLI entry point (async)
├── server.py            # HTTP API controller (FastAPI)
├── session.py           # Session entity + store (TTL, eviction)
├── config.py            # Centralized configuration
├── agent/
│   ├── orchestrator.py  # Async agentic loop + loop detection
│   ├── context.py       # Context window management
│   ├── prompt.py        # System prompt builder
│   └── display.py       # Terminal UI (Rich)
├── llm/
│   ├── port.py          # LLM interface (Protocol)
│   └── ollama.py        # Async Ollama client (httpx.AsyncClient)
├── tools/
│   ├── registry.py      # Tool registry + validation (Open/Closed)
│   ├── workspace.py     # File operations (sandboxed)
│   ├── browser.py       # Stealth web browser + search
│   └── system.py        # Code execution, date
├── logger/
│   └── logger.py        # JSONL audit logs
└── prompts/
    └── system.md        # System prompt
```

### Design principles

- **DDD** — domain logic in `agent/`, infrastructure in `llm/` and `logger/`, clear boundaries
- **SOLID** — single responsibility per module, open/closed tool registry, dependency inversion via `LLMPort` protocol
- **Async-first** — fully async LLM client with persistent connection pooling, no thread blocking
- **Performance** — quantized KV cache, flash attention, dynamic `num_predict`, uvloop

---

## Tools

| Tool | What it does |
|------|-------------|
| `write_file` | Create/overwrite files in workspace |
| `read_file` | Read files |
| `list_files` | List workspace contents |
| `delete_file` | Delete files or directories |
| `run_file` | Execute .py, .sh, .js scripts (30s timeout) |
| `get_date` | Current date and time |
| `web_search` | Search via DuckDuckGo |
| `web_read` | Read a page as clean markdown (httpx first, Playwright fallback) |
| `web_go` | Navigate and list interactive elements |
| `web_click` | Click buttons, links |
| `web_type` | Type into form fields |

### Add your own tool

Create a file in `app/tools/`, add your functions, then register them:

```python
# app/tools/my_tool.py
from app.tools import registry

def my_function(param: str) -> str:
    return f"Result: {param}"

def register_tools():
    registry.register("my_function", my_function,
        "Description of what it does.",
        {"type": "object", "properties": {
            "param": {"type": "string", "description": "What this param is"},
        }, "required": ["param"]})
```

Then add it to `app/tools/__init__.py`:

```python
from app.tools import workspace, system, browser, my_tool

def register_all():
    workspace.register_tools()
    system.register_tools()
    browser.register_tools()
    my_tool.register_tools()
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `API_MODEL` | `huihui_ai/qwen3.5-abliterated:4b` | Model to use |
| `API_CTX` | `8192` | Context window size (tokens) |
| `API_TOKEN` | — | Auth token (optional, for remote LLMs) |

### Ollama optimization (set as environment variables)

| Variable | Recommended | Effect |
|----------|-------------|--------|
| `OLLAMA_KEEP_ALIVE` | `-1` | Never unload model from memory |
| `OLLAMA_FLASH_ATTENTION` | `1` | Faster attention, lower memory |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | 50% KV cache memory savings |
| `OLLAMA_NUM_PARALLEL` | `1` | Single-user optimization |

---

## Run without Docker

```bash
# Install
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # edit as needed
```

### CLI (TUI mode)

Interactive terminal interface with Rich rendering (Markdown, colored tool calls, panels):

```bash
python -m app.main
```

### API server

```bash
uvicorn app.server:app --host 0.0.0.0 --port 8000 --loop uvloop
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
| **Sessions** | Multi-session API | Varies | Usually single |
| **Extensible** | Add tools in 1 file | No | Framework-dependent |
| **Async** | Full async pipeline | Varies | Rare |

---

## Contributing

PRs welcome. The tool registry is designed to be extended — add a new tool in one file, register it, done.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT
