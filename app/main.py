"""TUI client — connects to the nano-ai server via HTTP/SSE.

The server runs as a background worker. The TUI can disconnect and reconnect
without losing conversation state.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

SERVER_URL = os.getenv("AGENT_URL", "http://127.0.0.1:8000")
SERVER_PORT = SERVER_URL.rsplit(":", 1)[-1].split("/")[0]
SESSION_FILE = Path(".nano-session")

console = Console()


# --- Server management ---

async def _check_server() -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SERVER_URL}/health", timeout=3)
            return resp.json() if resp.status_code == 200 else None
    except (httpx.ConnectError, httpx.TimeoutException):
        return None


async def _ensure_server() -> dict | None:
    """Check if server is running, start it if not."""
    health = await _check_server()
    if health:
        return health

    console.print("[dim]Starting server...[/dim]")
    _stderr_log = tempfile.NamedTemporaryFile(prefix="nano-server-", suffix=".log", delete=False, mode="w")
    subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.server:app",
            "--host", "127.0.0.1", "--port", SERVER_PORT, "--log-level", "warning",
        ],
        stdout=subprocess.DEVNULL,
        stderr=_stderr_log,
    )

    for _ in range(15):
        await asyncio.sleep(1)
        health = await _check_server()
        if health:
            return health

    # Show server error log on failure
    try:
        with open(_stderr_log.name) as f:
            err = f.read().strip()
        if err:
            console.print(f"[red]Server stderr:[/red]\n[dim]{err[:500]}[/dim]")
    except Exception:
        pass
    return None


# --- Session persistence ---

def _load_session_id() -> str | None:
    if SESSION_FILE.exists():
        return SESSION_FILE.read_text().strip() or None
    return None


def _save_session_id(session_id: str) -> None:
    SESSION_FILE.write_text(session_id)


# --- History display on reconnect ---

async def _show_history(session_id: str) -> bool:
    """Fetch and display session history. Returns True if session exists."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SERVER_URL}/sessions/{session_id}/history", timeout=5)
            if resp.status_code != 200:
                return False

            data = resp.json()
            messages = data.get("messages", [])

            if not messages:
                return True

            # Show last 10 exchanges
            for msg in messages[-10:]:
                if msg["role"] == "user":
                    console.print(f"\n[bold]>> {msg['content']}[/bold]")
                elif msg["role"] == "assistant" and msg["content"]:
                    console.print(Markdown(msg["content"]))

            return True
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


async def _wait_if_busy(session_id: str) -> None:
    """Poll until the agent finishes its current task."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SERVER_URL}/sessions/{session_id}/history", timeout=5)
            if resp.status_code != 200 or not resp.json().get("busy"):
                return

        console.print("[yellow]Agent is still working on a previous request...[/yellow]")
        with console.status("[yellow]Waiting for agent...[/yellow]"):
            while True:
                await asyncio.sleep(2)
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{SERVER_URL}/sessions/{session_id}/history", timeout=5)
                    if resp.status_code != 200 or not resp.json().get("busy"):
                        break

        # Show the result
        await _show_history(session_id)
    except (httpx.ConnectError, httpx.TimeoutException):
        pass


# --- SSE rendering ---

def _render_event(event_type: str, data: dict, response_buf: list[str]) -> None:
    """Render a single SSE event to the terminal."""
    if event_type == "thinking":
        if not response_buf or response_buf[-1] != "__thinking__":
            console.print("[dim italic cyan]thinking...[/dim italic cyan]")
            response_buf.append("__thinking__")
        console.file.write(f"\033[2m\033[3m\033[36m{data.get('text', '')}\033[0m")
        console.file.flush()

    elif event_type == "response":
        text = data.get("text", "")
        # Clear thinking marker on first response chunk
        if response_buf and response_buf[-1] == "__thinking__":
            response_buf.pop()
            console.file.write("\033[0m\n")
            console.file.flush()
        response_buf.append(text)
        console.file.write(text)
        console.file.flush()

    elif event_type == "tool_call":
        text = Text()
        text.append("> ", style="bold yellow")
        text.append(data.get("name", ""), style="yellow")
        text.append(f"({json.dumps(data.get('args', {}), ensure_ascii=False)})", style="dim yellow")
        console.print(text)

    elif event_type == "tool_result":
        preview = data.get("result", "")[:200]
        if len(data.get("result", "")) > 200:
            preview += "..."
        console.print(f"  [dim]= {preview}[/dim]")

    elif event_type == "tool_error":
        console.print(f"  [bold red]{data.get('error', '')}[/bold red]")

    elif event_type == "status":
        console.print(f"  [dim cyan]{data.get('message', '')}[/dim cyan]")

    elif event_type == "stats":
        # Flush streamed response as rendered Markdown
        clean_parts = [p for p in response_buf if p != "__thinking__"]
        if clean_parts:
            full = "".join(clean_parts)
            line_count = full.count("\n") + 1
            for _ in range(line_count):
                console.file.write("\033[A\033[2K")
            console.file.flush()
            console.print(Markdown(full))
            response_buf.clear()

        parts = []
        if data.get("tps"):
            parts.append(f"{data['tps']} t/s")
        if data.get("tok"):
            parts.append(f"{data['tok']} tok")
        if data.get("ctx_pct"):
            parts.append(f"ctx {data['ctx_pct']}%")
        if parts:
            console.print(f"\n[dim]{' | '.join(parts)}[/dim]\n")

    elif event_type == "error":
        console.print(f"[bold red]Server error: {data.get('message', '')}[/bold red]")


async def _stream_chat(message: str, session_id: str | None) -> str | None:
    """Send a message and stream the response via SSE. Returns session ID."""
    payload: dict = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    result_session_id = session_id
    response_buf: list[str] = []

    try:
        console.print("[dim]  waiting...[/dim]")

        async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
            async with client.stream("POST", f"{SERVER_URL}/chat/stream", json=payload) as resp:
                if resp.status_code == 409:
                    await resp.aread()
                    console.print("[yellow]Agent is still busy. Wait for it to finish.[/yellow]")
                    return result_session_id

                if resp.status_code != 200:
                    await resp.aread()
                    console.print(f"[red]Server error: HTTP {resp.status_code}[/red]")
                    return result_session_id

                event_type = None
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        data = json.loads(line[6:])

                        if event_type == "session":
                            result_session_id = data.get("session_id")
                            if result_session_id:
                                _save_session_id(result_session_id)
                        elif event_type == "done":
                            break
                        elif event_type:
                            _render_event(event_type, data, response_buf)
    except KeyboardInterrupt:
        console.print("\n[dim](disconnected — agent continues in background)[/dim]")
    except httpx.ConnectError:
        console.print("[red]Lost connection to server.[/red]")

    return result_session_id


# --- Main loop ---

async def _run() -> None:
    health = await _ensure_server()
    if not health:
        console.print(f"[red]Cannot reach server at {SERVER_URL}[/red]")
        console.print("[dim]Start it with: uvicorn app.server:app --host 0.0.0.0 --port 8000[/dim]")
        sys.exit(1)

    model = health.get("model", "?")
    ctx = health.get("ctx", "?")
    ollama = health.get("ollama", "?")

    session_id = _load_session_id()
    reconnected = False

    if session_id:
        await _wait_if_busy(session_id)
        reconnected = await _show_history(session_id)
        if not reconnected:
            session_id = None

    status = "reconnected" if reconnected else f"ollama={ollama}"
    console.print(Panel(
        f"[dim]model={model} | ctx={ctx} | {status}[/dim]",
        title="[bold]Nano Agent[/bold]",
        border_style="dim",
        expand=False,
    ))
    console.print()

    while True:
        try:
            user_input = await asyncio.to_thread(input, ">> ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session paused. Agent stays alive on server.[/dim]")
            break

        if not user_input.strip():
            continue

        session_id = await _stream_chat(user_input, session_id)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
