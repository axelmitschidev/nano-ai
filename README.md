<p align="center">
  <img src="assets/banner.png" alt="nano-ai" width="600">
</p>

<h3 align="center">An autonomous AI agent that runs on your laptop.<br>2B parameters. Grade A.</h3>

<p align="center">
  <a href="https://github.com/axelmitschidev/nano-ai/stargazers"><img src="https://img.shields.io/github/stars/axelmitschidev/nano-ai?style=social" alt="Stars"></a>
  <a href="https://github.com/axelmitschidev/nano-ai/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/model-2B%20params-green.svg" alt="Model">
  <img src="https://img.shields.io/badge/E2E%20score-80%25%20Grade%20A-brightgreen.svg" alt="Benchmark">
  <img src="https://img.shields.io/badge/runs%20on-your%20machine-black.svg" alt="Local">
</p>

---

> A fully autonomous AI agent — browses the web, writes and runs code, manages files — powered by a **2B parameter model** running 100% locally. No cloud. No API key. No telemetry. **One command to install.**

---

## Benchmark — what a 2B model can actually do

We built an [end-to-end benchmark](e2e_bench.py) that tests the agent on real autonomous tasks, from simple chat to multi-step web research. Here are the results on a MacBook with **Qwen 3.5 2B**:

| Level | Task | Tools used | Time | Result |
|-------|------|-----------|------|--------|
| L1 | Answer a factual question | — | 11s | **PASS** |
| L1 | Use `get_date` tool | `get_date` | 10s | **PASS** |
| L2 | Write a file to workspace | `write_file` | 11s | **PASS** |
| L2 | Read back the file | `list_files → read_file` | 14s | **PASS** |
| L2 | List workspace contents | `list_files` | 8s | **PASS** |
| L3 | Write Python + execute it | `write_file → run_file` | 24s | **PASS** |
| L3 | Debug a buggy script | `list → read → write → run` | 47s | FAIL |
| L4 | Search the web | `web_search` | 31s | **PASS** |
| L4 | Read a web page + summarize | `web_read` | 32s | **PASS** |
| L5 | Compute primes + save results | `write → run → write` | 44s | **PASS** |
| L5 | Research + synthesize + save | `search → read → write` | 45s | **PASS** |

```
  10/11 tasks passed — 21 tok/s — peak context 38%

  ╔═══════════════════════════╗
  ║   GRADE:  A   (80/100)   ║
  ╚═══════════════════════════╝
```

Run it yourself: `.venv/bin/python e2e_bench.py`

---

## Quickstart

### Option 1 — Local (recommended)

```bash
# Install Ollama
brew install ollama        # macOS
# or: curl -fsSL https://ollama.com/install.sh | sh  # Linux

# Pull the model (~1.5 GB)
ollama pull huihui_ai/qwen3.5-abliterated:4b

# Clone and setup
git clone https://github.com/axelmitschidev/nano-ai.git
cd nano-ai
./setup.sh

# Launch
.venv/bin/python -m app.main
```

### Option 2 — Docker

```bash
git clone https://github.com/axelmitschidev/nano-ai.git && cd nano-ai

# Mac (Ollama must be running natively for Metal GPU)
docker compose --profile mac up -d --build

# Linux (Ollama included in container)
docker compose --profile linux up -d --build
```

### Option 3 — API only

```bash
.venv/bin/uvicorn app.server:app --host 0.0.0.0 --port 8000
```

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "search the web for the latest AI news and save a summary"}'
```

---

## What can it do?

| Capability | How |
|-----------|-----|
| **Browse the web** | Stealth Chromium browser that bypasses bot detection. Search, read, fill forms, click |
| **Write & run code** | Generates Python/JS, executes in sandbox, reads output, iterates |
| **Manage files** | Sandboxed workspace — create, read, delete, persist across sessions |
| **Multi-step reasoning** | Chains tool calls autonomously: search → read → analyze → write |
| **Self-correct** | Detects errors, retries, detects infinite loops, manages context window |
| **Stream in real-time** | SSE endpoint streams thinking, tool calls, and responses as they happen |

---

## How it works

```
User → "find Python news and save a summary"
         │
         ▼
   ┌─────────────┐
   │ Orchestrator │ ← ReAct loop (max 10 rounds)
   └──────┬──────┘
          │
          ├─→ web_search("Python news")     → results
          ├─→ web_read(best_url)            → markdown
          ├─→ write_file("summary.txt", …)  → saved
          │
          ▼
   "Done. Saved summary to summary.txt."
```

The orchestrator loops through **observe → think → act → observe** until the task is complete. It handles errors, retries, detects loops, and manages its own context window — all with a 2B model.

---

## Architecture

```
app/
├── main.py              # CLI with Rich TUI (connects via SSE)
├── server.py            # FastAPI + SSE streaming
├── session.py           # Session store (TTL, eviction, locks)
├── config.py            # Env-based configuration
├── agent/
│   ├── orchestrator.py  # ReAct loop + loop detection
│   ├── context.py       # Sliding window (atomic tool groups)
│   ├── prompt.py        # System prompt + memory injection
│   └── display.py       # Rich terminal rendering
├── llm/
│   ├── port.py          # LLM protocol (dependency inversion)
│   └── ollama.py        # Async Ollama client (httpx streaming)
├── tools/
│   ├── registry.py      # Open/Closed tool registry
│   ├── workspace.py     # Sandboxed file operations
│   ├── browser.py       # Stealth Playwright + DuckDuckGo
│   └── system.py        # Sandboxed code execution
└── prompts/
    └── system.md        # Agent persona + rules
```

**Design**: DDD boundaries, SOLID principles, fully async, dependency inversion via `LLMPort` protocol. Zero heavyweight frameworks — just httpx + FastAPI + Playwright.

---

## API

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/chat` | Send message, get response |
| `POST` | `/chat/stream` | SSE — real-time events (thinking, tool calls, response) |
| `GET` | `/sessions/{id}/history` | Retrieve conversation |
| `POST` | `/reset` | Clear a session |
| `GET` | `/health` | Status check |
| `GET` | `/docs` | Swagger UI |

```bash
# Start a conversation
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}' | jq
# → {"response": "Hi! How can I help?", "session_id": "abc-123"}

# Continue it
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what time is it?", "session_id": "abc-123"}' | jq
```

---

## Add your own tool — 1 file, 5 minutes

```python
# app/tools/my_tool.py
from app.tools import registry

def my_function(query: str) -> str:
    """Tools must return a string — the LLM reads it directly."""
    return f"Result for: {query}"

def register_tools():
    registry.register("my_function", my_function,
        "Description the LLM will see.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "The search query"},
        }, "required": ["query"]})
```

Then add one line to `app/tools/__init__.py`. Done.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `API_MODEL` | `huihui_ai/qwen3.5-abliterated:4b` | Model name |
| `API_CTX` | `8192` | Context window (tokens) |
| `API_TOKEN` | — | Auth token for remote LLMs |
| `API_THINK` | `false` | Enable model thinking/reflection |

---

## Why nano-ai?

| | nano-ai | ChatGPT / Claude | AutoGPT / CrewAI |
|---|---------|-------------------|-------------------|
| **Runs locally** | Yes | No | Needs API keys |
| **Cost** | Free forever | $20-200/mo | API costs |
| **Privacy** | 100% local | Your data on their servers | API calls logged |
| **Web browsing** | Stealth browser | Limited | Usually none |
| **Code execution** | Sandboxed | Restricted | Complex setup |
| **Model size** | 2-4B (~1.5GB) | 200B+ | 7-70B+ |
| **Setup time** | 2 minutes | Account + payment | Hours of config |
| **Extensible** | 1 file = 1 tool | No | Framework-dependent |
| **Works offline** | Yes (except web) | No | No |

---

## Contributing

PRs welcome. The tool registry is designed to be extended — add a new tool in one file, register it, done.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT
