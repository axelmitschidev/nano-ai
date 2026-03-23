"""Context window management — prevents overflow by trimming history."""

import json
from app.config import LLM_CTX, CTX_TRIM_RATIO

# Fixed overhead for tool schemas + safety margin (tokens)
_TOOL_SCHEMA_OVERHEAD = 1200

_COMPACTION_PROMPT = """Summarize this conversation concisely. Keep ONLY:
1. The user's original goal
2. Key results from tools (facts, not raw data)
3. Errors encountered (so they aren't repeated)
4. Current task state and next steps

Be brief. Max 300 words."""


def _token_cost(msg: dict) -> int:
    """Estimate token cost of a single message (conservative: len // 3)."""
    cost = len(msg.get("content", "") or "") // 3
    if msg.get("tool_calls"):
        cost += len(json.dumps(msg["tool_calls"])) // 3
    return cost


def estimate_messages(messages: list) -> int:
    return sum(_token_cost(msg) for msg in messages)


def _group_messages(messages: list[dict]) -> list[list[dict]]:
    """Group messages into atomic units: (assistant+tool_calls, tool results...) are one group."""
    groups: list[list[dict]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            group = [msg]
            i += 1
            while i < len(messages) and messages[i].get("role") == "tool":
                group.append(messages[i])
                i += 1
            groups.append(group)
        else:
            groups.append([msg])
            i += 1
    return groups


async def compact_with_llm(messages: list, llm) -> list:
    """Use the LLM to summarize old context when it's too large.
    Keeps system prompt + summary + last 5 messages."""
    system_msg = messages[0]
    recent = messages[-5:]
    old = messages[1:-5]

    if not old:
        return messages

    # Build text to summarize
    text_parts = []
    for m in old:
        role = m.get("role", "?")
        content = m.get("content", "")
        if content:
            text_parts.append(f"[{role}] {content[:200]}")
    conversation_text = "\n".join(text_parts)

    summary_messages = [
        {"role": "system", "content": _COMPACTION_PROMPT},
        {"role": "user", "content": conversation_text},
    ]

    summary = ""
    async for chunk in llm.chat(summary_messages, stream=True, tools=None):
        if "message" in chunk:
            summary += chunk["message"].get("content", "")

    summary = summary.strip()
    if not summary:
        return messages  # fallback: don't compact if summary failed

    summary_msg = {"role": "system", "content": f"[Context summary] {summary}"}
    return [system_msg, summary_msg] + recent


def trim(messages: list) -> list:
    """Sliding window: keep system prompt (index 0) + recent messages under budget.
    Tool call/result groups are treated as atomic units."""
    max_tokens = int(LLM_CTX * CTX_TRIM_RATIO) - _TOOL_SCHEMA_OVERHEAD
    current = estimate_messages(messages)

    if current <= max_tokens:
        return messages

    system_msg = messages[0]
    rest = messages[1:]

    # Phase 1: compact old tool results (adaptive threshold)
    ctx_pct = (current / max_tokens) * 100
    threshold = max(100, 600 - int(ctx_pct * 4))
    for i, msg in enumerate(rest):
        if current <= max_tokens:
            break
        content = msg.get("content", "") or ""
        if msg.get("role") == "tool" and len(content) > threshold:
            old = _token_cost(msg)
            rest[i] = {"role": "tool", "content": f"[result: {len(content)} chars] {content[:100]}..."}
            current -= old - _token_cost(rest[i])

    # Phase 2: drop oldest atomic groups (keep last 3 groups minimum)
    if current > max_tokens:
        groups = _group_messages(rest)
        while current > max_tokens and len(groups) > 3:
            removed_group = groups.pop(0)
            for msg in removed_group:
                current -= _token_cost(msg)
        rest = [msg for group in groups for msg in group]

    return [system_msg] + rest
