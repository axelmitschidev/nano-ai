"""Tool registry — registers, validates, and dispatches tool calls.

Open/Closed: new tools are added via register(), no modification needed.
"""

import inspect
from typing import Callable

_tools: dict[str, Callable] = {}
_definitions: list[dict] = []


def register(name: str, fn: Callable, description: str, parameters: dict):
    """Register a tool. Skips if already registered (idempotent)."""
    if name in _tools:
        return
    _tools[name] = fn
    _definitions.append({
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {**parameters, "additionalProperties": False},
        },
    })


def get_definitions() -> list[dict]:
    return _definitions


def get_fn(name: str) -> Callable | None:
    return _tools.get(name)


def list_names() -> list[str]:
    return list(_tools.keys())


def validate(tool_call: dict) -> tuple[bool, str | None]:
    """Validate a tool call before execution."""
    func = tool_call.get("function", {})
    name = func.get("name")
    args = func.get("arguments", {})

    if not name:
        return False, "ERROR: No tool name provided."

    if name not in _tools:
        return False, f"ERROR: Unknown tool '{name}'. Available: {', '.join(_tools.keys())}"

    for defn in _definitions:
        if defn["function"]["name"] == name:
            required = defn["function"]["parameters"].get("required", [])
            missing = [r for r in required if r not in args]
            if missing:
                return False, f"ERROR: '{name}' missing required args: {', '.join(missing)}"
            break

    return True, None


async def execute(tool_call: dict) -> str:
    """Validate and execute a tool call (supports sync and async tools)."""
    is_valid, error = validate(tool_call)
    if not is_valid:
        return error

    name = tool_call["function"]["name"]
    args = tool_call["function"]["arguments"]
    fn = _tools[name]

    try:
        result = fn(**args)
        if inspect.isawaitable(result):
            result = await result
        return result
    except TypeError as e:
        return f"ERROR: Bad arguments for '{name}': {e}"
    except Exception as e:
        return f"ERROR: {e}"
