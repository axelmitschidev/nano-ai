"""Persistent memory — JSONL-based key-value store in workspace."""

import json
import os
from datetime import datetime
from app.config import WORKSPACE_DIR

_MEMORY_PATH = os.path.join(WORKSPACE_DIR, "memory.jsonl")
_MAX_ENTRIES = 500


def remember(key: str, value: str) -> str:
    entry = {"ts": datetime.now().isoformat(), "key": key, "value": value}
    with open(_MEMORY_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _enforce_limit()
    return f"Remembered: {key}"


def recall(query: str) -> str:
    if not os.path.exists(_MEMORY_PATH):
        return "No memories found."
    results = []
    query_lower = query.lower()
    with open(_MEMORY_PATH, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if query_lower in entry.get("key", "").lower() or query_lower in entry.get("value", "").lower():
                    results.append(f"- {entry['key']}: {entry['value']}")
            except json.JSONDecodeError:
                continue
    if not results:
        return f"No memories matching '{query}'."
    return "\n".join(results[-20:])


def load_recent(n: int = 20) -> str:
    if not os.path.exists(_MEMORY_PATH):
        return ""
    entries = []
    with open(_MEMORY_PATH, "r") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not entries:
        return ""
    recent = entries[-n:]
    return "\n".join(f"- {e['key']}: {e['value']}" for e in recent)


def _enforce_limit():
    if not os.path.exists(_MEMORY_PATH):
        return
    with open(_MEMORY_PATH, "r") as f:
        lines = f.readlines()
    if len(lines) > _MAX_ENTRIES:
        with open(_MEMORY_PATH, "w") as f:
            f.writelines(lines[-_MAX_ENTRIES:])
