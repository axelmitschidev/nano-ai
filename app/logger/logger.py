"""Session logger — writes JSONL audit logs with persistent file handle."""

import json
import os
from datetime import datetime
from app.config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

_file_handle = None


def _get_handle():
    global _file_handle
    if _file_handle is None or _file_handle.closed:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(LOGS_DIR, f"session_{ts}.jsonl")
        _file_handle = open(path, "a")
    return _file_handle


def _log(event_type: str, **data):
    entry = {"ts": datetime.now().isoformat(), "type": event_type, **data}
    f = _get_handle()
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    f.flush()


def log_user(message: str):
    _log("user", content=message)


def log_thinking(content: str):
    _log("thinking", content=content)


def log_tool(name: str, args: dict, result: str):
    _log("tool", tool=name, args=args, result=result[:500])


def log_response(content: str):
    _log("response", content=content)


def log_error(error: str, context: str = ""):
    _log("error", error=error, context=context)


def close():
    global _file_handle
    if _file_handle and not _file_handle.closed:
        _file_handle.close()
    _file_handle = None
