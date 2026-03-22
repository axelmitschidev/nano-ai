"""System tools — date, code execution."""

import os
import subprocess
from datetime import datetime
from app.config import WORKSPACE_DIR
from app.tools import registry
from app.tools.workspace import _safe_path


def get_date() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_file(path: str) -> str:
    full = _safe_path(path)
    if not os.path.exists(full):
        return f"ERROR: '{path}' does not exist."

    ext_commands = {".py": ["python3", full], ".sh": ["bash", full], ".js": ["node", full]}

    cmd = None
    for ext, command in ext_commands.items():
        if path.endswith(ext):
            cmd = command
            break

    if not cmd:
        return "ERROR: unsupported extension. Use .py, .sh, or .js"

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=WORKSPACE_DIR,
        )
        # Truncate stdout first, then always append stderr + exit code
        stdout = result.stdout[:3000] if result.stdout else ""
        stderr = result.stderr[:800] if result.stderr else ""

        output = stdout
        if stderr:
            output += f"\n[stderr] {stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output if output.strip() else "(no output)"

    except subprocess.TimeoutExpired:
        return "ERROR: timeout (30s max)"
    except Exception as e:
        return f"ERROR: {e}"


def register_tools():
    registry.register("get_date", get_date,
        "Get the current date and time.",
        {"type": "object", "properties": {}, "required": []})

    registry.register("run_file", run_file,
        "Execute a script (.py, .sh, .js) and return its output.",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative path of script to run"},
        }, "required": ["path"]})
