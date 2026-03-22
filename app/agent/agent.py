"""Agent orchestration — the core agentic loop.

Single Responsibility: only handles the message loop and tool dispatch.
Depends on abstractions (registry, client, display) not implementations.
"""

import re
import json
from app.config import LLM_CTX, MAX_TOOL_ROUNDS, MAX_SILENT_RETRIES
from app.llm import client as llm
from app.tools import registry
from app.agent import display, context
from app.logger.logger import log_thinking, log_tool, log_response, log_error


def _try_parse_text_tool_call(text: str) -> dict | None:
    """Detect tool calls printed as text (Qwen 3.5 bug workaround)."""
    match = re.search(r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}', text)
    if match:
        try:
            name = match.group(1)
            args = json.loads(match.group(2))
            if registry.get_fn(name):
                return {"function": {"name": name, "arguments": args}}
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _collect_stream(chunks) -> tuple[dict, list]:
    """Consume the LLM stream, display in real-time, return (message, tool_calls)."""
    thinking_started = False
    responding_started = False
    full_content = ""
    full_thinking = ""
    tool_calls = []

    for chunk in chunks:
        if chunk.get("error"):
            display.print_tool_error(chunk["error"])
            log_error(chunk["error"], context="llm")
            continue

        if chunk.get("done"):
            stats = {}
            if chunk.get("eval_count") and chunk.get("eval_duration"):
                stats["tps"] = round(chunk["eval_count"] / (chunk["eval_duration"] / 1e9), 1)
                stats["tok"] = chunk["eval_count"]
            if chunk.get("prompt_eval_count"):
                stats["ctx_pct"] = round(chunk["prompt_eval_count"] / LLM_CTX * 100)
            if stats:
                display.print_stats(stats.get("tps", 0), stats.get("tok", 0), stats.get("ctx_pct", 0))
            continue

        if "message" not in chunk:
            continue

        msg = chunk["message"]
        thinking = msg.get("thinking", "")
        content = msg.get("content", "")

        if msg.get("tool_calls"):
            tool_calls.extend(msg["tool_calls"])

        if thinking:
            full_thinking += thinking
            if not thinking_started:
                thinking_started = True
                display.print_thinking_start()
            display.print_thinking(thinking)

        if content:
            full_content += content
            if not responding_started:
                responding_started = True
                display.print_response_start()
            display.print_response(content)

    if full_thinking:
        log_thinking(full_thinking)

    # Workaround: detect tool calls printed as text
    if not tool_calls and full_content:
        parsed = _try_parse_text_tool_call(full_content)
        if parsed:
            tool_calls.append(parsed)
            display.print_parsed_tool()
            full_content = ""

    assistant_msg = {"role": "assistant", "content": full_content}
    if tool_calls:
        assistant_msg["tool_calls"] = tool_calls
    return assistant_msg, tool_calls


def _execute_tool(tool_call: dict) -> str:
    """Validate, execute, display, and log a tool call."""
    is_valid, error = registry.validate(tool_call)
    if not is_valid:
        display.print_tool_error(error)
        log_error(error, context="validation")
        return error

    name = tool_call["function"]["name"]
    args = tool_call["function"]["arguments"]

    display.print_tool_call(name, args)
    result = registry.execute(tool_call)

    if result.startswith("ERROR"):
        display.print_tool_error(result)
    else:
        display.print_tool_result(result)

    log_tool(name, args, result)
    return result


def run_turn(user_input: str, history: list) -> list:
    """Run a single user turn: prompt → (tool loop) → response. Returns updated history."""
    messages = [*history, {"role": "user", "content": user_input}]
    tools = registry.get_definitions()
    silent_count = 0

    for _ in range(MAX_TOOL_ROUNDS):
        messages = context.trim(messages)

        chunks = llm.chat(messages, stream=True, think="low", tools=tools)
        assistant_msg, tool_calls = _collect_stream(chunks)
        messages.append(assistant_msg)

        if not tool_calls:
            if assistant_msg.get("content"):
                log_response(assistant_msg["content"])
                break

            silent_count += 1
            if silent_count >= MAX_SILENT_RETRIES:
                display.print_silent_fail(MAX_SILENT_RETRIES)
                log_error("Model silent after retries", context="orchestration")
                break

            display.print_retry(silent_count, MAX_SILENT_RETRIES)
            messages.append({"role": "user", "content": "You must respond now. Either call a tool or give your answer."})
            continue

        silent_count = 0
        for tc in tool_calls:
            result = _execute_tool(tc)
            messages.append({"role": "tool", "content": str(result)})
    else:
        display.print_round_limit(MAX_TOOL_ROUNDS)
        log_error("Tool rounds limit reached", context="orchestration")

    return messages
