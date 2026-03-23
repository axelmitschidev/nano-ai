"""Task planner — generates a step-by-step plan before execution."""

from app.llm.port import LLMPort
from app.tools import registry

_PLAN_PROMPT = """Break this task into 3-7 numbered steps. Each step should use one of these tools: {tools}.
If the task is simple (can be done in 1-2 steps), just list those steps.
Output ONLY the numbered list, nothing else."""


def needs_planning(user_input: str) -> bool:
    """Heuristic: plan if the task is complex."""
    if len(user_input) < 80:
        return False
    keywords = ["and", "then", "after", "save", "also", "finally", "next", "step"]
    lower = user_input.lower()
    return any(k in lower for k in keywords)


async def make_plan(llm: LLMPort, user_input: str) -> str | None:
    """Generate a plan for a complex task. Returns the plan text or None."""
    tool_names = ", ".join(registry.list_tool_names())
    messages = [
        {"role": "system", "content": _PLAN_PROMPT.format(tools=tool_names)},
        {"role": "user", "content": user_input},
    ]

    plan_text = ""
    async for chunk in llm.chat(messages, stream=True, tools=None):
        if chunk.get("error"):
            return None
        if "message" in chunk:
            plan_text += chunk["message"].get("content", "")

    plan_text = plan_text.strip()
    if not plan_text or len(plan_text) < 10:
        return None
    return plan_text
