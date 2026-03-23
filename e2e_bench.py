"""nano-ai End-to-End Benchmark — scores agent performance across 5 difficulty levels.

Metrics tracked per test:
  - latency_s:      total wall-clock time
  - tool_rounds:    number of tool calls made
  - tools_used:     list of tools invoked
  - tokens:         total tokens generated (from LLM stats)
  - tps:            tokens per second
  - ctx_pct:        context window usage %
  - completed:      whether the task goal was achieved (bool)
  - score:          0-100 composite score

Run:  .venv/bin/python e2e_bench.py
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

SERVER_URL = os.getenv("AGENT_URL", "http://127.0.0.1:8000")
WORKSPACE = Path(__file__).parent / "app" / "workspace"
TIMEOUT = 120  # max seconds per test


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class TestResult:
    name: str
    level: int
    description: str
    latency_s: float = 0.0
    tool_rounds: int = 0
    tools_used: list[str] = field(default_factory=list)
    tokens: int = 0
    tps: float = 0.0
    ctx_pct: int = 0
    completed: bool = False
    score: float = 0.0
    response: str = ""
    error: str = ""


@dataclass
class BenchReport:
    results: list[TestResult] = field(default_factory=list)
    total_score: float = 0.0
    max_score: float = 0.0
    grade: str = ""
    total_time: float = 0.0


# ── SSE client ───────────────────────────────────────────────────────

async def send_message(message: str, session_id: str | None = None) -> TestResult:
    """Send a message via SSE and collect all events + metrics."""
    result = TestResult(name="", level=0, description="")
    payload: dict = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    t0 = time.monotonic()
    full_response = []
    sid = session_id

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:
            async with client.stream("POST", f"{SERVER_URL}/chat/stream", json=payload) as resp:
                if resp.status_code != 200:
                    result.error = f"HTTP {resp.status_code}"
                    return result

                event_type = None
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        data = json.loads(line[6:])

                        if event_type == "session":
                            sid = data.get("session_id", sid)

                        elif event_type == "tool_call":
                            result.tool_rounds += 1
                            result.tools_used.append(data.get("name", "?"))

                        elif event_type == "response":
                            full_response.append(data.get("text", ""))

                        elif event_type == "stats":
                            result.tokens = data.get("tok", 0)
                            result.tps = data.get("tps", 0.0)
                            result.ctx_pct = data.get("ctx_pct", 0)

                        elif event_type == "error":
                            result.error = data.get("message", "")

                        elif event_type == "done":
                            break

    except httpx.TimeoutException:
        result.error = f"Timeout ({TIMEOUT}s)"
    except Exception as e:
        result.error = str(e)

    result.latency_s = round(time.monotonic() - t0, 2)
    result.response = "".join(full_response)
    return result


# ── Test definitions ─────────────────────────────────────────────────

TESTS: list[dict] = []


def test(level: int, name: str, description: str, weight: int = 10):
    """Decorator to register a test."""
    def decorator(fn):
        TESTS.append({
            "level": level,
            "name": name,
            "description": description,
            "weight": weight,
            "fn": fn,
        })
        return fn
    return decorator


# ── Level 1: Basic ───────────────────────────────────────────────────

@test(1, "Simple response", "Agent answers a factual question without tools", weight=5)
async def test_simple_response():
    r = await send_message("What is the capital of France? Answer in one word.")
    r.completed = "paris" in r.response.lower()
    return r


@test(1, "Get date", "Agent uses get_date tool correctly", weight=5)
async def test_get_date():
    r = await send_message("What is today's date? Use the get_date tool.")
    r.completed = "get_date" in r.tools_used and any(c.isdigit() for c in r.response)
    return r


# ── Level 2: File Operations ────────────────────────────────────────

@test(2, "Write file", "Agent writes a file to workspace", weight=8)
async def test_write_file():
    r = await send_message('Write a file called "bench_test.txt" with content "Hello from nano-ai benchmark"')
    target = WORKSPACE / "bench_test.txt"
    r.completed = (
        "write_file" in r.tools_used
        and target.exists()
        and "Hello" in target.read_text()
    )
    return r


@test(2, "Read file", "Agent reads back the file it wrote", weight=8)
async def test_read_file():
    r = await send_message("Read the file bench_test.txt and tell me its content.")
    r.completed = (
        "read_file" in r.tools_used
        and "hello" in r.response.lower()
    )
    return r


@test(2, "List files", "Agent lists workspace contents", weight=5)
async def test_list_files():
    r = await send_message("List all files in the workspace.")
    r.completed = (
        "list_files" in r.tools_used
        and "bench_test" in r.response.lower()
    )
    return r


# ── Level 3: Code Execution ─────────────────────────────────────────

@test(3, "Write + run Python", "Agent writes a Python script and executes it", weight=15)
async def test_write_and_run():
    r = await send_message(
        "Write a Python script called calc.py that prints the sum of numbers from 1 to 100, "
        "then execute it with run_file and tell me the result."
    )
    r.completed = (
        "write_file" in r.tools_used
        and "run_file" in r.tools_used
        and "5050" in r.response
    )
    return r


@test(3, "Debug + fix", "Agent writes buggy code, gets error, fixes it", weight=15)
async def test_debug_fix():
    # Pre-write a buggy script
    buggy = WORKSPACE / "buggy.py"
    buggy.write_text('print("result:", 10 / 0)\n')
    r = await send_message(
        "Run the file buggy.py. If it has an error, fix it so it prints 'result: 42' instead, "
        "then run it again."
    )
    r.completed = (
        "run_file" in r.tools_used
        and ("write_file" in r.tools_used or "42" in r.response)
        and "42" in r.response
    )
    return r


# ── Level 4: Web ─────────────────────────────────────────────────────

@test(4, "Web search", "Agent searches the web and reports results", weight=10)
async def test_web_search():
    r = await send_message("Search the web for 'Python programming language' and give me the top 3 results.")
    r.completed = (
        "web_search" in r.tools_used
        and len(r.response) > 50
    )
    return r


@test(4, "Web read", "Agent reads a web page and extracts info", weight=12)
async def test_web_read():
    r = await send_message("Read the page https://httpbin.org/html and summarize what you see.")
    r.completed = (
        ("web_read" in r.tools_used or "web_go" in r.tools_used)
        and len(r.response) > 30
    )
    return r


# ── Level 5: Complex Multi-step ─────────────────────────────────────

@test(5, "Multi-step: compute + save", "Write script → run → save output to file", weight=20)
async def test_multi_step_compute():
    r = await send_message(
        "Write a Python script called primes.py that finds all prime numbers below 50. "
        "Execute it, then save the output to a file called primes_result.txt."
    )
    result_file = WORKSPACE / "primes_result.txt"
    r.completed = (
        "write_file" in r.tools_used
        and "run_file" in r.tools_used
        and result_file.exists()
        and any(str(p) in result_file.read_text() for p in [2, 7, 13, 23, 47])
    )
    return r


@test(5, "Autonomous research", "Search + read + synthesize + save", weight=20)
async def test_autonomous_research():
    r = await send_message(
        "Search the web for 'what is FastAPI Python', read the most relevant result, "
        "write a short summary (3-5 sentences) and save it to fastapi_summary.txt."
    )
    summary_file = WORKSPACE / "fastapi_summary.txt"
    r.completed = (
        "web_search" in r.tools_used
        and ("web_read" in r.tools_used or "web_go" in r.tools_used)
        and "write_file" in r.tools_used
        and summary_file.exists()
        and len(summary_file.read_text()) > 50
    )
    return r


# ── Scoring ──────────────────────────────────────────────────────────

def score_result(r: TestResult, weight: int) -> float:
    """Score a single test result (0 to weight)."""
    if not r.completed:
        return 0.0

    s = weight  # start at max

    # Latency penalty: lose up to 30% for slow responses
    if r.latency_s > 60:
        s *= 0.7
    elif r.latency_s > 30:
        s *= 0.85

    # Efficiency bonus/penalty: fewer tool rounds = better
    if r.level <= 2 and r.tool_rounds > 5:
        s *= 0.9
    elif r.level >= 3 and r.tool_rounds > 8:
        s *= 0.9

    # Context usage penalty: >80% = cutting it close
    if r.ctx_pct > 80:
        s *= 0.9

    return round(s, 1)


def compute_grade(pct: float) -> str:
    if pct >= 90: return "A+"
    if pct >= 80: return "A"
    if pct >= 70: return "B"
    if pct >= 60: return "C"
    if pct >= 40: return "D"
    return "F"


# ── Runner ───────────────────────────────────────────────────────────

def print_header():
    print()
    print("=" * 78)
    print("  nano-ai  E2E BENCHMARK")
    print("=" * 78)
    print()


def print_result(r: TestResult, weight: int):
    status = "✓ PASS" if r.completed else "✗ FAIL"
    color = "\033[32m" if r.completed else "\033[31m"
    reset = "\033[0m"

    print(f"  {color}{status}{reset}  L{r.level} | {r.name}")
    print(f"         {r.description}")

    metrics = []
    metrics.append(f"{r.latency_s}s")
    if r.tool_rounds:
        metrics.append(f"{r.tool_rounds} tools")
    if r.tokens:
        metrics.append(f"{r.tokens} tok")
    if r.tps:
        metrics.append(f"{r.tps} t/s")
    if r.ctx_pct:
        metrics.append(f"ctx {r.ctx_pct}%")
    metrics.append(f"score: {r.score}/{weight}")

    print(f"         \033[2m{' | '.join(metrics)}\033[0m")

    if r.tools_used:
        print(f"         \033[2mtools: {' → '.join(r.tools_used)}\033[0m")

    if r.error:
        print(f"         \033[31merror: {r.error[:100]}\033[0m")

    print()


def print_report(report: BenchReport):
    pct = (report.total_score / report.max_score * 100) if report.max_score else 0

    print("=" * 78)
    print("  RESULTS")
    print("=" * 78)
    print()

    # Per-level breakdown
    levels = {}
    for r in report.results:
        if r.level not in levels:
            levels[r.level] = {"passed": 0, "total": 0, "score": 0, "max": 0}
        levels[r.level]["total"] += 1
        levels[r.level]["passed"] += int(r.completed)
        t = next(t for t in TESTS if t["name"] == r.name)
        levels[r.level]["score"] += r.score
        levels[r.level]["max"] += t["weight"]

    level_names = {1: "Basic", 2: "File Ops", 3: "Code Exec", 4: "Web", 5: "Complex"}
    print(f"  {'Level':<20} {'Pass':>6} {'Score':>10} {'Pct':>8}")
    print(f"  {'─' * 20} {'─' * 6} {'─' * 10} {'─' * 8}")
    for lv in sorted(levels):
        d = levels[lv]
        lpct = (d["score"] / d["max"] * 100) if d["max"] else 0
        print(f"  L{lv} {level_names.get(lv, ''):<17} {d['passed']}/{d['total']:>3} {d['score']:>6.1f}/{d['max']:<3} {lpct:>6.1f}%")

    print(f"  {'─' * 20} {'─' * 6} {'─' * 10} {'─' * 8}")
    print(f"  {'TOTAL':<20} "
          f"{sum(d['passed'] for d in levels.values())}/{sum(d['total'] for d in levels.values()):>3} "
          f"{report.total_score:>6.1f}/{report.max_score:<3.0f} "
          f"{pct:>6.1f}%")
    print()

    # Aggregate metrics
    completed = [r for r in report.results if r.completed]
    if completed:
        avg_lat = sum(r.latency_s for r in completed) / len(completed)
        avg_tools = sum(r.tool_rounds for r in completed) / len(completed)
        avg_tps = sum(r.tps for r in completed if r.tps) / max(len([r for r in completed if r.tps]), 1)
        total_tok = sum(r.tokens for r in completed)
        max_ctx = max((r.ctx_pct for r in completed), default=0)

        print(f"  Avg latency:       {avg_lat:.1f}s")
        print(f"  Avg tool rounds:   {avg_tools:.1f}")
        print(f"  Avg throughput:    {avg_tps:.1f} tok/s")
        print(f"  Total tokens:      {total_tok}")
        print(f"  Peak context:      {max_ctx}%")
    print(f"  Total time:        {report.total_time:.1f}s")
    print()

    # Grade
    print(f"  ╔═══════════════════════════════╗")
    print(f"  ║  GRADE:  {report.grade:<3}   ({pct:.0f}/100)     ║")
    print(f"  ╚═══════════════════════════════╝")
    print()


async def run_benchmark():
    print_header()

    # Check server
    print("  Checking server...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SERVER_URL}/health", timeout=5)
            health = resp.json()
            print(f"  Server: {health.get('status', '?')} | Model: {health.get('model', '?')} | "
                  f"Ctx: {health.get('ctx', '?')} | Ollama: {health.get('ollama', '?')}")
    except Exception as e:
        print(f"  \033[31mServer not reachable at {SERVER_URL}: {e}\033[0m")
        print(f"  Start with: .venv/bin/uvicorn app.server:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

    print()
    print("─" * 78)
    print()

    # Clean workspace before tests
    for f in WORKSPACE.glob("bench_test*"):
        f.unlink()
    for f in WORKSPACE.glob("calc*"):
        f.unlink()
    for f in WORKSPACE.glob("buggy*"):
        f.unlink()
    for f in WORKSPACE.glob("primes*"):
        f.unlink()
    for f in WORKSPACE.glob("fastapi_summary*"):
        f.unlink()

    report = BenchReport()
    t_global = time.monotonic()

    # Use a single session for all tests (tests context memory too)
    session_id = None

    for t in TESTS:
        r: TestResult = await t["fn"]()
        r.name = t["name"]
        r.level = t["level"]
        r.description = t["description"]
        r.score = score_result(r, t["weight"])
        report.results.append(r)
        report.max_score += t["weight"]
        report.total_score += r.score

        print_result(r, t["weight"])

    report.total_time = round(time.monotonic() - t_global, 1)
    report.grade = compute_grade(report.total_score / report.max_score * 100 if report.max_score else 0)

    print_report(report)

    # Save report as JSON
    report_path = Path(__file__).parent / "bench_report.json"
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": health.get("model", "?"),
        "ctx": health.get("ctx", "?"),
        "grade": report.grade,
        "score": report.total_score,
        "max_score": report.max_score,
        "pct": round(report.total_score / report.max_score * 100, 1) if report.max_score else 0,
        "total_time_s": report.total_time,
        "tests": [
            {
                "name": r.name,
                "level": r.level,
                "completed": r.completed,
                "score": r.score,
                "latency_s": r.latency_s,
                "tool_rounds": r.tool_rounds,
                "tools_used": r.tools_used,
                "tokens": r.tokens,
                "tps": r.tps,
                "ctx_pct": r.ctx_pct,
                "error": r.error,
            }
            for r in report.results
        ],
    }
    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
    print(f"  Report saved to: {report_path}")
    print()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
