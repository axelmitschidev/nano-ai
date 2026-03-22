"""Tools package — auto-registers all tool modules."""

from app.tools import workspace, system, browser


def register_all():
    """Register all tools from every module."""
    workspace.register_tools()
    system.register_tools()
    browser.register_tools()
