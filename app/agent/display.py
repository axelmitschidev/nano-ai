"""Terminal display — handles all ANSI formatting and output."""

import json

DIM = "\033[2m"
ITALIC = "\033[3m"
RESET = "\033[0m"
CYAN = "\033[36m"
BOLD = "\033[1m"
YELLOW = "\033[33m"
RED = "\033[31m"


def print_banner(model: str, ctx: int):
    print(f"{DIM}Nano agent ready. ctx={ctx} | model={model}{RESET}\n")


def print_thinking_start():
    print(f"{DIM}{ITALIC}{CYAN}thinking...{RESET}")
    print(f"{DIM}{ITALIC}{CYAN}", end="")


def print_thinking(text: str):
    print(text, end="", flush=True)


def print_response_start():
    print(f"{RESET}\n{BOLD}", end="")


def print_response(text: str):
    print(text, end="", flush=True)


def print_stats(tps: float, tok: int, ctx_pct: int):
    parts = [f"{tps} t/s", f"{tok} tok", f"ctx {ctx_pct}%"]
    print(f"{RESET}\n")
    print(f"{DIM}{' | '.join(parts)}{RESET}")
    print()


def print_tool_call(name: str, args: dict):
    print(f"{DIM}{YELLOW}> {name}({json.dumps(args, ensure_ascii=False)}){RESET}")


def print_tool_result(result: str):
    preview = result[:200] + ("..." if len(result) > 200 else "")
    print(f"{DIM}  = {preview}{RESET}")


def print_tool_error(error: str):
    print(f"{RED}  {error}{RESET}")


def print_retry(count: int, max_retries: int):
    print(f"{DIM}{YELLOW}(retry {count}/{max_retries}...){RESET}")


def print_silent_fail(max_retries: int):
    print(f"{DIM}{RED}(model silent after {max_retries} retries){RESET}")


def print_round_limit(limit: int):
    print(f"{RED}Tool rounds limit ({limit}) reached.{RESET}")


def print_parsed_tool():
    print(f"\n{DIM}{YELLOW}(parsed tool call from text){RESET}")


def print_end():
    print(f"\n{DIM}Session ended.{RESET}")
