"""Persistent memory — loads workspace/memory.md into the system prompt."""

import os
from app.config import WORKSPACE_DIR, PROMPT_PATH


def load_system_prompt() -> str:
    """Build the full system prompt with memory injected if available."""
    with open(PROMPT_PATH, "r") as f:
        prompt = f.read()

    memory_path = os.path.join(WORKSPACE_DIR, "memory.md")
    if os.path.exists(memory_path):
        with open(memory_path, "r") as f:
            memory = f.read().strip()
        if memory:
            prompt += f"\n\n## Memory (from previous sessions)\n{memory}"

    return prompt
