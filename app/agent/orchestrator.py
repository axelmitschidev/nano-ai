"""Agent orchestrator — the core agentic loop.

Single Responsibility: runs the message loop, dispatches tools, detects loops.
Dependency Inversion: depends on LLMPort protocol, not a concrete client.
"""

import asyncio
import json
import re
from app.config import LLM_CTX, LLM_THINK, MAX_TOOL_ROUNDS, MAX_SILENT_RETRIES, MAX_LOOP_DETECT
from app.llm.port import LLMPort
from app.tools import registry
from app.agent import display, context
from app.logger.logger import log_thinking, log_tool, log_response, log_error


EventSink = asyncio.Queue | None

# Tags for synthetic messages that should be cleaned from history
_SYNTHETIC_TAG = "__synthetic__"


def _emit(sink: EventSink, event: str, data: dict) -> None:
    """Push an event to the sink if one is active (non-blocking)."""
    if sink is not None:
        sink.put_nowait({"event": event, "data": data})


def _try_parse_text_tool_call(text: str) -> dict | None:
    """Detect tool calls printed as text (Qwen 3.5 bug workaround).
    Only matches when the JSON structure starts near the beginning of the content."""
    # Only look at the first 200 chars for the tool call pattern start
    prefix = text[:200]
    match = re.search(r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:', prefix)
    if not match:
        return None

    name = match.group(1)
    if not registry.get_fn(name):
        return None

    # Parse the full JSON object starting from the match
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text[match.start():])
        if isinstance(obj, dict) and "arguments" in obj and isinstance(obj["arguments"], dict):
            return {"function": {"name": name, "arguments": obj["arguments"]}}
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _detect_loop(tool_calls_history: list[list[str]], current_round: list[str]) -> bool:
    """Detect if the same set of tool calls has been made N consecutive rounds."""
    if len(tool_calls_history) < MAX_LOOP_DETECT:
        return False
    recent = tool_calls_history[-MAX_LOOP_DETECT:]
    return all(r == current_round for r in recent)


async def _collect_stream(chunks, sink: EventSink = None) -> tuple[dict, list[dict]]:
    """Consume the async LLM stream, display in real-time, return (message, tool_calls)."""
    thinking_started = False
    responding_started = False
    full_content = ""
    full_thinking = ""
    tool_calls = []

    async for chunk in chunks:
        if chunk.get("error"):
            display.print_tool_error(chunk["error"])
            log_error(chunk["error"], context="llm")
            _emit(sink, "tool_error", {"error": chunk["error"]})
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
                _emit(sink, "stats", stats)
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
            _emit(sink, "thinking", {"text": thinking})

        if content:
            full_content += content
            if not responding_started:
                responding_started = True
                display.print_response_start()
            display.print_response(content)
            _emit(sink, "response", {"text": content})

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


async def _execute_tool(tool_call: dict, sink: EventSink = None) -> str:
    """Validate, execute, display, and log a single tool call."""
    is_valid, error = registry.validate(tool_call)
    if not is_valid:
        display.print_tool_error(error)
        log_error(error, context="validation")
        _emit(sink, "tool_error", {"error": error})
        return error

    name = tool_call["function"]["name"]
    args = tool_call["function"]["arguments"]

    display.print_tool_call(name, args)
    _emit(sink, "tool_call", {"name": name, "args": args})

    result = await registry.execute(tool_call)

    if result.startswith("ERROR"):
        display.print_tool_error(result)
        _emit(sink, "tool_error", {"error": result})
    else:
        display.print_tool_result(result)
        _emit(sink, "tool_result", {"result": result[:500]})

    log_tool(name, args, result)
    return result


def _clean_history(messages: list[dict]) -> list[dict]:
    """Remove synthetic orchestration messages (nudges, loop warnings) from history."""
    return [m for m in messages if not m.get(_SYNTHETIC_TAG)]


async def run_turn(
    llm: LLMPort,
    user_input: str,
    history: list[dict],
    event_sink: EventSink = None,
) -> list[dict]:
    """Run a single user turn: prompt → (tool loop) → response. Returns updated history."""
    messages = [*history, {"role": "user", "content": user_input}]
    tools = registry.get_definitions()
    silent_count = 0
    round_history: list[list[str]] = []

    loop_detected = False

    for _ in range(MAX_TOOL_ROUNDS):
        messages = context.trim(messages)

        active_tools = None if loop_detected else tools
        chunks = llm.chat(messages, stream=True, think=LLM_THINK, tools=active_tools)
        assistant_msg, tool_calls = await _collect_stream(chunks, event_sink)
        messages.append(assistant_msg)

        if not tool_calls:
            if assistant_msg.get("content"):
                log_response(assistant_msg["content"])
                break

            if loop_detected:
                display.print_silent_fail(0)
                log_error("Model silent after loop detection", context="orchestration")
                break

            silent_count += 1
            if silent_count >= MAX_SILENT_RETRIES:
                display.print_silent_fail(MAX_SILENT_RETRIES)
                log_error("Model silent after retries", context="orchestration")
                break

            display.print_retry(silent_count, MAX_SILENT_RETRIES)
            nudge = {"role": "system", "content": "Respond now. Either call a tool or answer the user.", _SYNTHETIC_TAG: True}
            messages.append(nudge)
            continue

        if loop_detected:
            log_error("Model called tools after loop detection, ending turn", context="loop_detection")
            break

        silent_count = 0

        # Build round keys for loop detection
        current_round_keys = []
        for tc in tool_calls:
            current_round_keys.append(json.dumps(tc.get("function", {}), sort_keys=True))

        if _detect_loop(round_history, current_round_keys):
            loop_msg = f"Loop detected: same tool calls repeated {MAX_LOOP_DETECT} times. Answer with what you have."
            display.print_tool_error(loop_msg)
            _emit(event_sink, "tool_error", {"error": loop_msg})
            msg = {"role": "system", "content": loop_msg, _SYNTHETIC_TAG: True}
            messages.append(msg)
            log_error(loop_msg, context="loop_detection")
            loop_detected = True
            # Still execute this round's tool calls to avoid orphaned tool_calls
            for tc in tool_calls:
                result = await _execute_tool(tc, event_sink)
                messages.append({"role": "tool", "content": str(result)})
            round_history.append(current_round_keys)
            continue

        round_history.append(current_round_keys)
        for tc in tool_calls:
            result = await _execute_tool(tc, event_sink)
            messages.append({"role": "tool", "content": str(result)})
    else:
        display.print_round_limit(MAX_TOOL_ROUNDS)
        log_error("Tool rounds limit reached", context="orchestration")

    return _clean_history(messages)
