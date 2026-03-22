"""Terminal display — Rich-based formatting and output."""

import json
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

console = Console()

# Buffer for streaming response — rendered as Markdown at flush time
_response_buf: list[str] = []


def print_banner(model: str, ctx: int):
    console.print(
        Panel(
            f"[dim]ctx={ctx} | model={model}[/dim]",
            title="[bold]Nano Agent[/bold]",
            border_style="dim",
            expand=False,
        )
    )
    console.print()


def print_thinking_start():
    console.print("[dim italic cyan]thinking...[/dim italic cyan]")


def print_thinking(text: str):
    console.file.write(f"\033[2m\033[3m\033[36m{text}\033[0m")
    console.file.flush()


def print_response_start():
    console.file.write("\033[0m\n")
    console.file.flush()
    _response_buf.clear()


def print_response(text: str):
    _response_buf.append(text)
    console.file.write(text)
    console.file.flush()


def _flush_response():
    """Render accumulated response as Markdown."""
    full = "".join(_response_buf)
    _response_buf.clear()
    if not full.strip():
        return
    # Move cursor up to overwrite raw streamed text: clear lines then print Markdown
    line_count = full.count("\n") + 1
    for _ in range(line_count):
        console.file.write("\033[A\033[2K")
    console.file.flush()
    console.print(Markdown(full))


def print_stats(tps: float, tok: int, ctx_pct: int):
    _flush_response()
    parts = [f"{tps} t/s", f"{tok} tok", f"ctx {ctx_pct}%"]
    console.print(f"\n[dim]{' | '.join(parts)}[/dim]\n")


def print_tool_call(name: str, args: dict):
    text = Text()
    text.append("> ", style="bold yellow")
    text.append(name, style="yellow")
    text.append(f"({json.dumps(args, ensure_ascii=False)})", style="dim yellow")
    console.print(text)


def print_tool_result(result: str):
    preview = result[:200] + ("..." if len(result) > 200 else "")
    console.print(f"  [dim]= {preview}[/dim]")


def print_tool_error(error: str):
    console.print(f"  [bold red]{error}[/bold red]")


def print_retry(count: int, max_retries: int):
    console.print(f"[dim yellow](retry {count}/{max_retries}...)[/dim yellow]")


def print_silent_fail(max_retries: int):
    console.print(f"[dim red](model silent after {max_retries} retries)[/dim red]")


def print_round_limit(limit: int):
    console.print(f"[red]Tool rounds limit ({limit}) reached.[/red]")


def print_parsed_tool():
    console.print("\n[dim yellow](parsed tool call from text)[/dim yellow]")


def print_end():
    console.print("\n[dim]Session ended.[/dim]")
