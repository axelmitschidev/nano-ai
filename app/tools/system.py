"""System tools — date, code execution."""

import os
import signal
import subprocess
from datetime import datetime
from app.config import WORKSPACE_DIR
from app.tools import registry
from app.tools.workspace import _safe_path

# Minimal env for sandboxed execution — no API_TOKEN or host secrets leak
_SAFE_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": WORKSPACE_DIR,
    "LANG": os.environ.get("LANG", "en_US.UTF-8"),
}


def get_date() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_file(path: str) -> str:
    full = _safe_path(path)
    if not os.path.exists(full):
        return f"ERROR: '{path}' does not exist."

    ext_commands = {
        ".py": ["python3", full],
        ".js": ["node", full],
    }

    cmd = None
    for ext, command in ext_commands.items():
        if path.endswith(ext):
            cmd = command
            break

    if not cmd:
        return "ERROR: unsupported extension. Use .py or .js"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=WORKSPACE_DIR,
            env=_SAFE_ENV,
            start_new_session=True,
        )
        stdout = result.stdout[:3000] if result.stdout else ""
        stderr = result.stderr[:800] if result.stderr else ""

        output = stdout
        if stderr:
            output += f"\n[stderr] {stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output if output.strip() else "(no output)"

    except subprocess.TimeoutExpired as e:
        # Kill entire process group to clean up any children
        try:
            os.killpg(e.args[0] if isinstance(e.args[0], int) else os.getpgid(e.args[0].pid), signal.SIGKILL)
        except (ProcessLookupError, OSError, AttributeError):
            pass
        return "ERROR: timeout (30s max)"
    except Exception as e:
        return f"ERROR: {e}"


_ALLOWED_COMMANDS = frozenset({
    "python3", "node", "pip", "cat", "ls", "head", "tail", "wc",
    "sort", "grep", "find", "curl", "jq", "echo", "date", "mkdir", "cp", "mv",
})

_DANGEROUS_PATTERNS = frozenset({"|", ";", "&&", "||", "`", "$(", "${", ">", "<", ">>", "<<"})


def run_command(command: str) -> str:
    parts = command.strip().split()
    if not parts:
        return "ERROR: empty command."

    cmd_name = os.path.basename(parts[0])
    if cmd_name not in _ALLOWED_COMMANDS:
        return f"ERROR: '{cmd_name}' is not allowed. Allowed: {', '.join(sorted(_ALLOWED_COMMANDS))}"

    for pattern in _DANGEROUS_PATTERNS:
        if pattern in command:
            return f"ERROR: '{pattern}' is not allowed in commands for security."

    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=WORKSPACE_DIR,
            env=_SAFE_ENV,
            start_new_session=True,
        )
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
        "Execute a script (.py, .js) and return its output. Max 30s.",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative path of script to run"},
        }, "required": ["path"]})

    registry.register("run_command", run_command,
        "Run a shell command in the workspace. Allowed: python3, node, pip, cat, ls, head, tail, wc, sort, grep, find, curl, jq, echo, date, mkdir, cp, mv.",
        {"type": "object", "properties": {
            "command": {"type": "string", "description": "The command to run (e.g. 'pip install requests', 'curl https://...')"},
        }, "required": ["command"]})
