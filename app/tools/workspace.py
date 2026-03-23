"""Workspace tools — file system operations sandboxed to the workspace directory."""

import os
import shutil
from app.config import WORKSPACE_DIR
from app.tools import registry


def _safe_path(path: str) -> str:
    """Resolve path and ensure it stays within the workspace (realpath for symlink safety)."""
    full = os.path.realpath(os.path.join(WORKSPACE_DIR, path))
    if not full.startswith(os.path.realpath(WORKSPACE_DIR)):
        raise PermissionError(f"Access denied: {path} is outside workspace")
    return full


_BINARY_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".exe", ".dll", ".so", ".dylib", ".wasm", ".pyc"})


def _sanitize_code(content: str, path: str) -> str:
    """Fix common LLM code generation issues (smart quotes, etc.) for all text files."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _BINARY_EXTENSIONS:
        return content
    content = content.replace("\u2018", "'").replace("\u2019", "'")
    content = content.replace("\u201c", '"').replace("\u201d", '"')
    content = content.replace("\u2013", "-").replace("\u2014", "--")
    return content


def write_file(path: str, content: str) -> str:
    full = _safe_path(path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    content = _sanitize_code(content, path)
    with open(full, "w") as f:
        f.write(content)
    return f"File '{path}' written."


def read_file(path: str) -> str:
    full = _safe_path(path)
    if not os.path.exists(full):
        return f"ERROR: '{path}' does not exist."
    with open(full, "r") as f:
        content = f.read()
    if len(content) > 4000:
        content = content[:4000] + "\n[... truncated ...]"
    return content


def list_files() -> str:
    files = []
    for root, dirs, filenames in os.walk(WORKSPACE_DIR):
        rel_root = os.path.relpath(root, WORKSPACE_DIR)
        for d in dirs:
            dir_path = os.path.join(rel_root, d) if rel_root != "." else d
            files.append(f"[dir] {dir_path}/")
        for name in filenames:
            if name == ".gitkeep":
                continue
            file_path = os.path.join(rel_root, name) if rel_root != "." else name
            files.append(file_path)
    if not files:
        return "Workspace is empty."
    return "\n".join(files)


def delete_file(path: str) -> str:
    full = _safe_path(path)
    if not os.path.exists(full):
        return f"ERROR: '{path}' does not exist."
    if os.path.isdir(full):
        shutil.rmtree(full)
        return f"Directory '{path}' deleted."
    os.remove(full)
    return f"File '{path}' deleted."


def register_tools():
    registry.register("write_file", write_file,
        "Create or overwrite a file in the workspace.",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative file path"},
            "content": {"type": "string", "description": "File content"},
        }, "required": ["path", "content"]})

    registry.register("read_file", read_file,
        "Read a file from the workspace.",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative file path"},
        }, "required": ["path"]})

    registry.register("list_files", list_files,
        "List all files and directories in the workspace.",
        {"type": "object", "properties": {}, "required": []})

    registry.register("delete_file", delete_file,
        "Delete a file or directory from the workspace.",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative path to delete"},
        }, "required": ["path"]})
