"""Context window management — prevents overflow by trimming history."""

import json
from app.config import LLM_CTX, CTX_TRIM_RATIO


def estimate_tokens(text: str) -> int:
    """Rough estimate: ~3 chars per token for mixed content."""
    return len(text) // 3


def estimate_messages(messages: list) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        if msg.get("tool_calls"):
            total += estimate_tokens(json.dumps(msg["tool_calls"]))
    return total


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
            old = estimate_tokens(msg["content"])
            rest[i] = {"role": "tool", "content": "[truncated]"}
            current -= old - 5

    # Phase 2: drop oldest (keep last 6)
    while current > max_tokens and len(rest) > 6:
        removed = rest.pop(0)
        current -= estimate_tokens(removed.get("content", ""))

    return [system_msg] + rest
