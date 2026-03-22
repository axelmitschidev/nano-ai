"""Session logger — writes JSONL audit logs."""

import json
import os
from datetime import datetime
from app.config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

_session_path: str | None = None


def _get_path() -> str:
    global _session_path
    if not _session_path:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _session_path = os.path.join(LOGS_DIR, f"session_{ts}.jsonl")
    return _session_path


def _log(event_type: str, **data):
    entry = {"timestamp": datetime.now().isoformat(), "type": event_type, **data}
    with open(_get_path(), "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_user(message: str):
    _log("user", content=message)


def log_thinking(content: str):
    _log("thinking", content=content)


def log_tool(name: str, args: dict, result: str):
    _log("tool", tool=name, args=args, result=result)


def log_response(content: str):
    _log("response", content=content)


def log_error(error: str, context: str = ""):
    _log("error", error=error, context=context)
