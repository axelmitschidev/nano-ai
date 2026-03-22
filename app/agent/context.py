"""Context window management — prevents overflow by trimming history."""

import json
from app.config import LLM_CTX, CTX_TRIM_RATIO


def _token_cost(msg: dict) -> int:
    """Estimate token cost of a single message."""
    cost = len(msg.get("content", "")) // 4
    if msg.get("tool_calls"):
        cost += len(json.dumps(msg["tool_calls"])) // 4
    return cost


def estimate_messages(messages: list) -> int:
    return sum(_token_cost(msg) for msg in messages)


def trim(messages: list) -> list:
    """Sliding window: keep system prompt (index 0) + recent messages under budget."""
    max_tokens = int(LLM_CTX * CTX_TRIM_RATIO)
    current = estimate_messages(messages)

    if current <= max_tokens:
        return messages

    system_msg = messages[0]
    rest = messages[1:]

    # Phase 1: compact old tool results
    for i, msg in enumerate(rest):
        if current <= max_tokens:
            break
        if msg.get("role") == "tool" and len(msg.get("content", "")) > 200:
            old = _token_cost(msg)
            rest[i] = {"role": "tool", "content": "[truncated]"}
            current -= old - 3

    # Phase 2: drop oldest (keep last 6)
    while current > max_tokens and len(rest) > 6:
        removed = rest.pop(0)
        current -= _token_cost(removed)

    return [system_msg] + rest
