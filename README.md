<p align="center">
  <img src="assets/banner.png" alt="nano-ai" width="600">
</p>

<h3 align="center">An autonomous AI agent that runs on your laptop.<br>4B parameters. 13/14 autonomous tasks passed.</h3>

<p align="center">
  <a href="https://github.com/axelmitschidev/nano-ai/stargazers"><img src="https://img.shields.io/github/stars/axelmitschidev/nano-ai?style=social" alt="Stars"></a>
  <a href="https://github.com/axelmitschidev/nano-ai/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/model-4B%20params-green.svg" alt="Model">
  <img src="https://img.shields.io/badge/E2E-13%2F14%20tasks%20passed-brightgreen.svg" alt="Benchmark">
  <img src="https://img.shields.io/badge/runs%20on-your%20machine-black.svg" alt="Local">
</p>

---

> A fully autonomous AI agent — plans tasks, browses the web, writes and runs code, remembers across sessions — powered by a **4B parameter model** running 100% locally. No cloud. No API key. No telemetry. **One script to install.**

---

## Quickstart

```bash
git clone https://github.com/axelmitschidev/nano-ai.git
cd nano-ai
./setup.sh            # checks Ollama, pulls model, installs deps + browser
.venv/bin/python -m app.main
```

Requires [Ollama](https://ollama.com) (local LLM runtime). `setup.sh` checks for it, pulls the model (~3 GB), creates the venv, and installs dependencies + Chromium.

<details>
<summary>Docker alternative</summary>

```bash
# Mac (Ollama must be running natively for Metal GPU)
docker compose --profile mac up -d --build

# Linux (Ollama included in container)
docker compose --profile linux up -d --build
```

</details>

<details>
<summary>API mode</summary>

```bash
.venv/bin/uvicorn app.server:app --host 0.0.0.0 --port 8000
```

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "search the web for the latest AI news and save a summary"}'
```

</details>

---

## What can it do?

| Capability | How |
|-----------|-----|
| **Plan & execute** | Breaks complex tasks into steps before acting (Plan-then-Execute) |
| **Browse the web** | Stealth Chromium browser. Search, read pages, fill forms, click buttons |
| **Write & run code** | Generates Python/JS, executes in sandbox, reads output, iterates |
| **Run shell commands** | Controlled shell access: pip, curl, grep, jq, etc. (allowlist-based) |
| **Manage files** | Sandboxed workspace — create, read, delete, persist across sessions |
| **Remember** | Persistent memory across sessions — saves and recalls facts automatically |
| **Track progress** | Agent scratchpad for long tasks — notes what's done and what's next |
| **Self-correct** | Error-guided retry with strategy hints, loop detection, context compaction |
| **Stream in real-time** | SSE endpoint streams thinking, tool calls, and responses live |
| **Adapt to any model** | Auto-detects model family (Qwen, Llama, Mistral, Phi, Gemma, DeepSeek) |

---

## Benchmark

We built an [end-to-end benchmark](e2e_bench.py) that tests the agent on real autonomous tasks across 6 difficulty levels. Results on a MacBook with **Qwen 3.5 4B**:

| Level | Task | Tools used | Result |
|-------|------|-----------|--------|
| L1 | Answer a factual question | — | **PASS** |
| L1 | Use `get_date` tool | `get_date` | **PASS** |
| L2 | Write a file to workspace | `write_file` | **PASS** |
| L2 | Read back the file | `read_file` | **PASS** |
| L2 | List workspace contents | `list_files` | **PASS** |
| L3 | Write Python + execute it | `write_file → run_file` | **PASS** |
| L3 | Debug a buggy script | `read → write → run` | **PASS** |
| L4 | Search the web | `web_search` | **PASS** |
| L4 | Read a web page + summarize | `web_read` | **PASS** |
| L5 | Compute primes + save results | `write → run → read` | **PASS** |
| L5 | Research + synthesize + save | `search → read → write` | **PASS** |
| L6 | Plan a multi-step research task | `search → read → write → run` | **PASS** |
| L6 | Remember facts across conversation | `remember → recall` | **PASS** |
| L6 | Use shell commands for data tasks | `run_command` | FAIL |

```
  13/14 tasks passed — 7.1 tok/s — peak context 52%
```

Run it yourself (start the server first): `.venv/bin/python e2e_bench.py`

---

## How it works

```
User → "find Python news and save a summary"
         │
         ▼
   ┌─────────────┐
   │   Planner    │ ← breaks task into steps (if complex)
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │ Orchestrator │ ← ReAct loop (max 10 rounds)
   └──────┬──────┘
          │
          ├─→ web_search("Python news")     → results
          ├─→ web_read(best_url)            → markdown
          ├─→ write_file("summary.txt", …)  → saved
          ├─→ remember("task", "done")      → persisted
          │
          ▼
   "Done. Saved summary to summary.txt."
```

The agent **plans** complex tasks before executing, then loops through **observe → think → act → observe** until done. It handles errors with strategy hints, detects loops, compacts context via LLM when the window fills up, and remembers across sessions.

---

## Architecture

```
app/
├── main.py              # CLI client (connects via SSE)
├── server.py            # FastAPI + SSE streaming
├── session.py           # Session store (TTL, eviction, locks)
├── config.py            # Env-based configuration
├── agent/
│   ├── orchestrator.py  # ReAct loop + parallel tools + loop detection
│   ├── planner.py       # Plan-then-Execute for complex tasks
│   ├── context.py       # Sliding window + LLM compaction
│   ├── memory.py        # Persistent memory + scratchpad
│   ├── prompt.py        # System prompt + memory injection
│   └── display.py       # Terminal rendering (Rich)
├── llm/
│   ├── port.py          # LLM protocol (swappable backend)
│   ├── ollama.py        # Async Ollama client (httpx streaming)
│   └── profiles.py      # Auto-detected model profiles
├── tools/
│   ├── registry.py      # Tool registry (add tools without touching core)
│   ├── workspace.py     # Sandboxed file operations
│   ├── browser.py       # Stealth Playwright + DuckDuckGo
│   └── system.py        # Code execution + shell commands
├── logger/
│   └── logger.py        # JSONL audit logs
└── prompts/
    ├── system.md        # Default agent prompt (structured)
    ├── coder.md         # Coding-focused profile
    └── researcher.md    # Research-focused profile
```

Fully async. Each module does one thing. The LLM backend is swappable — implement `chat()` and `close()`, plug it in.

---

## Tools

| Tool | What it does |
|------|-------------|
| `web_search` | Search via DuckDuckGo |
| `web_read` | Read a page as clean markdown (smart extraction) |
| `web_go` | Navigate and list interactive elements |
| `web_click` | Click buttons, links |
| `web_type` | Type into form fields |
| `write_file` | Create/overwrite files in workspace |
| `read_file` | Read files (4000 char cap) |
| `list_files` | List workspace contents |
| `delete_file` | Delete files or directories |
| `run_file` | Execute .py/.js scripts (30s timeout, sandboxed) |
| `run_command` | Shell commands: pip, curl, grep, jq, ls, etc. (allowlist) |
| `get_date` | Current date and time |
| `remember` | Save a fact to persistent memory |
| `recall` | Search persistent memory |
| `note_progress` | Track progress on long tasks (read/append/clear) |

---

## Under the hood

| Feature | What it does |
|---------|-------------|
| **Plan-then-Execute** | Complex tasks get a 3-7 step plan before the agent starts acting |
| **Context compaction** | When context hits 80%, the LLM summarizes old messages to free space |
| **Parallel tool execution** | Independent tools (reads, searches) run simultaneously via `asyncio.gather` |
| **Dynamic tool filtering** | Only shows relevant tools per round (web tools during browsing, file tools during editing) |
| **Error-guided retry** | When a tool fails, the agent gets a strategy hint (timeout → simplify, not found → list first) |
| **Temperature scheduling** | 0.05 for code, 0.1 for tool calls, 0.3 for chat, 0.25 for retries |
| **Model auto-detection** | Detects Qwen, Llama, Mistral, Phi, Gemma, DeepSeek — adjusts stop tokens and workarounds |
| **Loop detection** | Detects repeated tool call patterns at the round level, forces the agent to answer |

---

## API

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/chat` | Send message, get response |
| `POST` | `/chat/stream` | SSE — real-time events (thinking, tool calls, response) |
| `GET` | `/sessions/{id}/history` | Retrieve conversation |
| `POST` | `/reset?session_id=xxx` | Clear a session |
| `GET` | `/health` | Status check |
| `GET` | `/docs` | Swagger UI |

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}' | jq
```

---

## Add your own tool

Create one file, register it, done:

```python
# app/tools/my_tool.py
from app.tools import registry

def my_function(query: str) -> str:
    return f"Result for: {query}"

def register_tools():
    registry.register("my_function", my_function,
        "Description the LLM sees when choosing tools.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "The search query"},
        }, "required": ["query"]})
```

Then add one line to `app/tools/__init__.py`.

---

## Configuration

### LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `API_MODEL` | `huihui_ai/qwen3.5-abliterated:4b` | Model name (any Ollama model works) |
| `API_CTX` | `8192` | Context window (tokens) |
| `API_TOKEN` | — | Auth token for remote LLMs |
| `API_THINK` | `false` | Enable model thinking/reflection |

### Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_PLAN` | `true` | Enable task planning for complex requests |
| `AGENT_MEMORY` | `true` | Enable persistent memory |
| `AGENT_PROFILE` | `default` | Prompt profile (`default`, `coder`, `researcher`) |
| `AGENT_MAX_ROUNDS` | `10` | Max tool rounds per turn |
| `AGENT_MAX_RETRIES` | `2` | Max silent retries |
| `AGENT_CTX_TRIM` | `0.75` | Context trim ratio |

---

## Why nano-ai?

| | nano-ai | ChatGPT / Claude | AutoGPT / CrewAI |
|---|---------|-------------------|-------------------|
| **Runs locally** | Yes | No | Needs API keys |
| **Cost** | Free | $20-200/mo | API costs |
| **Privacy** | 100% local | Your data on their servers | API calls logged |
| **Web browsing** | Stealth browser | Yes (limited) | Varies |
| **Code execution** | Sandboxed | Restricted | Complex setup |
| **Persistent memory** | Yes | Limited | Framework-dependent |
| **Task planning** | Yes (auto) | Yes | Manual setup |
| **Model size** | 4B (~3GB) | 200B+ | 7-70B+ |
| **Setup time** | ~5 minutes | Account + payment | Hours of config |
| **Extensible** | 1 file = 1 tool | No | Framework-dependent |
| **Works offline** | Yes (except web) | No | No |

---

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT
