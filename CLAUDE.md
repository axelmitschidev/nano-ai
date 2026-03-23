# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is this project

nano-ai is an autonomous AI agent that runs locally via Ollama (Qwen 3.5 4B). It has a stealth web browser (Playwright), a sandboxed file workspace, and code execution. Two entry points: a FastAPI HTTP API (`server.py`) and an interactive CLI (`main.py`). The agent loops through tool calls until the task is done (ReAct pattern).

## Commands

```bash
# Lint (must pass before any push)
ruff check app/

# Run API server locally
uvicorn app.server:app --host 0.0.0.0 --port 8000 --loop uvloop

# Run CLI mode
python -m app.main

# Docker — Mac (requires Ollama installed natively for Metal GPU)
docker compose --profile mac up -d --build

# Docker — Linux/CI (Ollama + agent both in containers)
docker compose --profile linux up -d --build

# Build Docker image only
docker build -t nano-ai .

# CI checks — there is no test suite, CI validates imports + lint + docker build
ruff check app/
python -c "from app.tools import register_all; register_all(); print('OK')"
python -c "from app.agent.prompt import load_system_prompt; print(load_system_prompt()[:50])"
python -c "from app.agent.context import trim; print('OK')"
python -c "from app.llm.ollama import OllamaClient; print('OK')"
python -c "from app.session import SessionStore; print('OK')"
python -c "from app.server import app; print('OK')"
```

## Branch workflow

`main` is protected — requires PR with 3 passing CI checks (lint, test, docker). Never push directly.
All work goes through `dev`. Branch from `dev`, PR into `dev`, then PR `dev` → `main`.
On merge to `main`, deploy.yml auto-tags a release `v1.0.0-<sha>`.

## Architecture — how the pieces connect

### Request lifecycle (the critical path)

```
POST /chat (server.py)
  → SessionStore.get_or_create()     # app/session.py — in-memory, TTL 1h, max 100
  → async with session.lock           # one request at a time per session
  → await run_turn(llm, msg, history) # app/agent/orchestrator.py
      → for each round (max MAX_TOOL_ROUNDS=10):
          context.trim(messages)       # sliding window: compact tool results, then drop oldest
          llm.chat(messages, tools=…)  # async stream via OllamaClient
          _collect_stream(chunks)      # real-time display + extract tool_calls
          if tool_calls → registry.execute() each → append result → loop
          if content → done
          if silent → inject nudge message → retry (max 2)
  → return last assistant message
```

### Dependency Inversion — the LLM boundary

The orchestrator depends on `LLMPort` (Protocol in `app/llm/port.py`), not on `OllamaClient` directly. To add a new LLM backend, implement `chat()` (async generator yielding dicts) and `close()`. The orchestrator doesn't care what's behind the protocol.

`OllamaClient` (`app/llm/ollama.py`) uses a persistent `httpx.AsyncClient` with connection pooling. Key behavior:
- `keep_alive: -1` (integer) → model stays loaded permanently in Ollama
- `num_predict` is dynamic: 512 when tools are present (tool JSON is short), 1024 for chat responses
- Streaming: yields newline-delimited JSON chunks from Ollama's `/api/chat`

### Tool system

Tools are the agent's hands. Every tool function **must return a `str`** — the LLM reads tool results directly as message content.

**Registry** (`app/tools/registry.py`): module-level `_tools` dict and `_definitions` list. Tools register via `registry.register(name, fn, description, json_schema)`. Registration is idempotent (skips duplicates). Validation checks required args before execution.

**Adding a tool**: create `app/tools/my_tool.py` with functions + `register_tools()`, then add it to `app/tools/__init__.py`'s `register_all()`.

**Existing tool modules**:
- `workspace.py` — file CRUD, sandboxed via `_safe_path()` (realpath check against `WORKSPACE_DIR`). `_sanitize_code()` fixes LLM smart quotes in code files.
- `browser.py` — Playwright stealth browser (lazy-launched on first use). `web_read` tries plain httpx first, falls back to full browser. `web_go`/`web_click`/`web_type` for interactive navigation. `_get_elements()` extracts up to 50 visible interactive elements with auto-generated CSS selectors. DuckDuckGo search via `ddgs` library.
- `system.py` — `get_date` and `run_file` (subprocess with 30s timeout, sandboxed to workspace, stripped env vars, process group kill on timeout). Shell scripts (.sh) disabled for security.

### Qwen 3.5 workaround

`_try_parse_text_tool_call()` in `orchestrator.py` exists because Qwen 3.5 sometimes outputs tool calls as plain text JSON instead of using the structured tool_calls format. The function uses regex + `json.JSONDecoder.raw_decode` to extract them.

### Context management

`app/agent/context.py` — two-phase sliding window, called every loop iteration:
1. Compact old tool results >200 chars to `[truncated]`
2. Drop oldest messages (keep last 6 minimum)

Token estimation is `len(content) // 3` (conservative). Budget = `LLM_CTX * CTX_TRIM_RATIO` (75%) minus 1200 tokens tool schema overhead. Tool call/result groups are trimmed as atomic units to preserve message sequence validity. System prompt (messages[0]) is never trimmed.

### Session lifecycle

`app/session.py` — `Session` entity (uses `__slots__`) holds history + asyncio.Lock. `SessionStore` manages creation, TTL eviction (1h), LRU eviction at cap (100), and a background cleanup task every 5 min. Each session starts with the system prompt loaded from `app/prompts/system.md` + optional workspace memory (`app/workspace/memory.md`).

### Logging

`app/logger/logger.py` — JSONL audit logs with persistent file handle. One file per server startup (`session_<timestamp>.jsonl` in `app/logs/`). Events: `user`, `thinking`, `tool`, `response`, `error`. Tool results are truncated to 500 chars in logs.

### Display

`app/agent/display.py` — ANSI terminal output (thinking in cyan italic, responses in bold, tools in yellow dim, errors in red). Only used in CLI mode but also called by the orchestrator during API requests (logs to server stdout).

## Docker setup

Two compose profiles:
- **`mac`**: agent container only, connects to Ollama on host via `host.docker.internal:11434`. Required because Docker on macOS cannot access the Metal GPU — Ollama must run natively for GPU acceleration.
- **`linux`**: Ollama + agent containers. Ollama pulls the model on first start via `scripts/ollama-entrypoint.sh`. Healthcheck waits for model to appear in `ollama list`.

Ollama optimization env vars (in `linux` profile): `OLLAMA_KEEP_ALIVE=-1`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`.

Dockerfile runs `uvicorn` with 1 worker (single process — browser and logger use module-level state), uvloop event loop, httptools HTTP parser.

## Configuration

All config in `app/config.py` via env vars (`.env` file loaded by python-dotenv):
- `API_URL` — Ollama endpoint (default: `http://localhost:11434/api/chat`)
- `API_MODEL` — model name (default: `huihui_ai/qwen3.5-abliterated:4b`)
- `API_CTX` — context window in tokens (default: `8192`)
- `API_TOKEN` — optional auth token for remote LLMs

Hardcoded agent constants in `config.py`: `MAX_TOOL_ROUNDS=10`, `MAX_SILENT_RETRIES=2`, `CTX_TRIM_RATIO=0.75`, `MAX_LOOP_DETECT=2`.

## Code conventions

- DDD-oriented, SOLID principles. One concern per module.
- Async-first: the entire LLM→orchestrator→server chain is async. No `run_in_executor`.
- Type hints on signatures. Module-level docstrings. No per-function docstrings unless non-obvious.
- Linter: `ruff check app/` must pass.
- Dependencies: stdlib + httpx + playwright + fastapi + ddgs + html2text + python-dotenv. No heavy frameworks.
- Respond in French when communicating with the user.
