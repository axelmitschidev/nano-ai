"""Tools package — auto-registers all tool modules."""

from app.tools import workspace, system, browser
from app.agent import memory as agent_memory
from app.tools import registry


def register_all():
    """Register all tools from every module."""
    workspace.register_tools()
    system.register_tools()
    browser.register_tools()
    # Memory tools
    registry.register("remember", agent_memory.remember,
        "Save a fact to persistent memory. Use this to remember important information across sessions.",
        {"type": "object", "properties": {
            "key": {"type": "string", "description": "Short label for the memory (e.g. 'user_name', 'project_goal')"},
            "value": {"type": "string", "description": "The information to remember"},
        }, "required": ["key", "value"]})
    registry.register("recall", agent_memory.recall,
        "Search persistent memory for previously saved information.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search term to find in memory"},
        }, "required": ["query"]})
