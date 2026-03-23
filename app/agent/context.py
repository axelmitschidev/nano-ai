"""Context window management — prevents overflow by trimming history."""

import json
from app.config import LLM_CTX, CTX_TRIM_RATIO

# Fixed overhead for tool schemas + safety margin (tokens)
_TOOL_SCHEMA_OVERHEAD = 1200


def _token_cost(msg: dict) -> int:
    """Estimate token cost of a single message (conservative: len // 3)."""
    cost = len(msg.get("content", "") or "") // 3
    if msg.get("tool_calls"):
        cost += len(json.dumps(msg["tool_calls"])) // 3
    return cost


def estimate_messages(messages: list) -> int:
    return sum(_token_cost(msg) for msg in messages)


def _group_messages(messages: list[dict]) -> list[list[dict]]:
    """Group messages into atomic units: (assistant+tool_calls, tool results...) are one group.
    Standalone messages are their own group."""
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


def trim(messages: list) -> list:
    """Sliding window: keep system prompt (index 0) + recent messages under budget.
    Tool call/result groups are treated as atomic units."""
    max_tokens = int(LLM_CTX * CTX_TRIM_RATIO) - _TOOL_SCHEMA_OVERHEAD
    current = estimate_messages(messages)

    if current <= max_tokens:
        return messages

    system_msg = messages[0]
    rest = messages[1:]

    # Phase 1: compact old tool results (preserve pairing)
    for i, msg in enumerate(rest):
        if current <= max_tokens:
            break
        if msg.get("role") == "tool" and len(msg.get("content", "") or "") > 200:
            old = _token_cost(msg)
            rest[i] = {"role": "tool", "content": "[truncated]"}
            current -= old - 3

    # Phase 2: drop oldest atomic groups (keep last 6 messages minimum)
    if current > max_tokens:
        groups = _group_messages(rest)
        while current > max_tokens and len(groups) > 3:
            removed_group = groups.pop(0)
            for msg in removed_group:
                current -= _token_cost(msg)
        rest = [msg for group in groups for msg in group]

    return [system_msg] + rest
