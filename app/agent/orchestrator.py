"""Agent orchestrator — the core agentic loop.

Single Responsibility: runs the message loop, dispatches tools, detects loops.
Dependency Inversion: depends on LLMPort protocol, not a concrete client.
"""

import asyncio
import json
import re
from app.config import LLM_CTX, LLM_MODEL, LLM_THINK, MAX_TOOL_ROUNDS, MAX_SILENT_RETRIES, MAX_LOOP_DETECT, AGENT_PLAN, CTX_TRIM_RATIO
from app.llm.port import LLMPort
from app.llm.profiles import detect_profile
from app.tools import registry
from app.agent import display, context
from app.logger.logger import log_thinking, log_tool, log_response, log_error

_model_profile = detect_profile(LLM_MODEL)

EventSink = asyncio.Queue | None

_SYNTHETIC_TAG = "__synthetic__"

# Error-guided retry hints
_ERROR_HINTS: dict[str, str] = {
    "timeout": "Try a simpler approach or reduce the scope.",
    "not found": "Use list_files first to check what exists.",
    "not exist": "Use list_files first to check what exists.",
    "permission": "Check the file path — it must be inside the workspace.",
    "HTTP": "Try a different URL or use web_search to find alternatives.",
    "connection": "The site may be down. Try web_search for an alternative source.",
}


def _categorize_tool(name: str) -> str:
    if name.startswith("web_"):
        return "web"
    if name.endswith("_file") or name == "list_files":
        return "file"
    return "system"


def _filter_tools(tools: list[dict], used_categories: list[str]) -> list[dict]:
    if not used_categories:
        return tools
    last_cat = used_categories[-1]
    always_keep = {"get_date", "list_files", "remember", "recall"}
    return [
        t for t in tools
        if _categorize_tool(t["function"]["name"]) == last_cat
        or t["function"]["name"] in always_keep
    ]


def _emit(sink: EventSink, event: str, data: dict) -> None:
    if sink is not None:
        sink.put_nowait({"event": event, "data": data})


def _try_parse_text_tool_call(text: str) -> dict | None:
    """Detect tool calls printed as text (model-specific workaround)."""
    prefix = text[:200]
    match = re.search(r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:', prefix)
    if not match:
        return None
    name = match.group(1)
    if not registry.get_fn(name):
        return None
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text[match.start():])
        if isinstance(obj, dict) and "arguments" in obj and isinstance(obj["arguments"], dict):
            return {"function": {"name": name, "arguments": obj["arguments"]}}
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _detect_loop(tool_calls_history: list[list[str]], current_round: list[str]) -> bool:
    if len(tool_calls_history) < MAX_LOOP_DETECT:
        return False
    recent = tool_calls_history[-MAX_LOOP_DETECT:]
    return all(r == current_round for r in recent)


def _inject_error_hint(error_result: str, messages: list[dict]) -> None:
    lower = error_result.lower()
    for key, hint in _ERROR_HINTS.items():
        if key.lower() in lower:
            messages.append({"role": "system", "content": f"Hint: {hint}", _SYNTHETIC_TAG: True})
            return


def _can_parallelize(tool_calls: list[dict]) -> bool:
    if len(tool_calls) <= 1:
        return False
    names = [tc.get("function", {}).get("name", "") for tc in tool_calls]
    writers = {"write_file", "delete_file", "run_file", "run_command"}
    return not any(n in writers for n in names)


async def _collect_stream(chunks, sink: EventSink = None) -> tuple[dict, list[dict]]:
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

    # Model-specific text tool call workaround
    if not tool_calls and full_content and _model_profile["text_tool_fix"]:
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

    _slow_tools = {"web_read", "web_go", "web_click", "web_search", "run_file", "run_command"}
    if name in _slow_tools:
        _emit(sink, "status", {"message": f"executing {name}..."})

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
    return [m for m in messages if not m.get(_SYNTHETIC_TAG)]


async def run_turn(
    llm: LLMPort,
    user_input: str,
    history: list[dict],
    event_sink: EventSink = None,
) -> list[dict]:
    messages = [*history, {"role": "user", "content": user_input}]
    tools = registry.get_definitions()
    silent_count = 0
    round_history: list[list[str]] = []
    used_categories: list[str] = []
    last_tool_name = ""

    loop_detected = False

    # Plan-then-Execute for complex tasks
    if AGENT_PLAN:
        from app.agent.planner import needs_planning, make_plan
        if needs_planning(user_input):
            _emit(event_sink, "status", {"message": "planning..."})
            plan = await make_plan(llm, user_input)
            if plan:
                plan_msg = {"role": "system", "content": f"Your plan:\n{plan}\n\nExecute step by step.", _SYNTHETIC_TAG: True}
                messages.append(plan_msg)
                _emit(event_sink, "status", {"message": f"plan ready ({len(plan.splitlines())} steps)"})

    compacted = False

    for round_num in range(MAX_TOOL_ROUNDS):
        # LLM-based compaction when context is very full (once per turn)
        ctx_usage = context.estimate_messages(messages) / (LLM_CTX * CTX_TRIM_RATIO)
        if ctx_usage > 0.80 and not compacted:
            _emit(event_sink, "status", {"message": "compacting context..."})
            messages = await context.compact_with_llm(messages, llm)
            compacted = True
        messages = context.trim(messages)

        # Temperature phase
        if silent_count > 0:
            phase = "retry"
        elif not used_categories:
            phase = "chat"
        elif last_tool_name in ("write_file", "run_file", "run_command"):
            phase = "code"
        else:
            phase = "tool"

        active_tools = None if loop_detected else _filter_tools(tools, used_categories)
        ctx_used = context.estimate_messages(messages)

        if round_num > 0:
            _emit(event_sink, "status", {"message": "reasoning..."})

        chunks = llm.chat(
            messages, stream=True, think=LLM_THINK, tools=active_tools,
            ctx_used=ctx_used, phase=phase,
        )
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
            for tc in tool_calls:
                name = tc.get("function", {}).get("name", "")
                result = await _execute_tool(tc, event_sink)
                messages.append({"role": "tool", "content": str(result)})
                used_categories.append(_categorize_tool(name))
                last_tool_name = name
                if result.startswith("ERROR"):
                    _inject_error_hint(result, messages)
            round_history.append(current_round_keys)
            continue

        round_history.append(current_round_keys)

        # Parallel execution when safe
        if _can_parallelize(tool_calls):
            results = await asyncio.gather(*[_execute_tool(tc, event_sink) for tc in tool_calls])
            for i, result in enumerate(results):
                name = tool_calls[i].get("function", {}).get("name", "")
                messages.append({"role": "tool", "content": str(result)})
                used_categories.append(_categorize_tool(name))
                last_tool_name = name
                if result.startswith("ERROR"):
                    _inject_error_hint(result, messages)
        else:
            for tc in tool_calls:
                name = tc.get("function", {}).get("name", "")
                result = await _execute_tool(tc, event_sink)
                messages.append({"role": "tool", "content": str(result)})
                used_categories.append(_categorize_tool(name))
                last_tool_name = name
                if result.startswith("ERROR"):
                    _inject_error_hint(result, messages)
    else:
        display.print_round_limit(MAX_TOOL_ROUNDS)
        log_error("Tool rounds limit reached", context="orchestration")

    return _clean_history(messages)
