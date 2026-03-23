"""System prompt builder — loads the base prompt and injects workspace memory."""

import os
from app.config import PROMPT_PATH, AGENT_PROFILE


def load_system_prompt() -> str:
    """Build the full system prompt with memory injected if available."""
    # Try profile-specific prompt first
    if AGENT_PROFILE != "default":
        profile_path = os.path.join(os.path.dirname(PROMPT_PATH), f"{AGENT_PROFILE}.md")
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                prompt = f.read()
            from app.agent.memory import load_recent
            recent = load_recent(20)
            if recent:
                prompt += f"\n\n## Memory (from previous sessions)\n{recent}"
            return prompt

    with open(PROMPT_PATH, "r") as f:
        prompt = f.read()

    # Load persistent memory
    from app.agent.memory import load_recent
    recent = load_recent(20)
    if recent:
        prompt += f"\n\n## Memory (from previous sessions)\n{recent}"

    return prompt
