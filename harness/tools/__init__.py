"""The tool registry: which tools exist, and which are switched on."""
from __future__ import annotations

from harness.config import Settings
from harness.tools import files, knowledge, network, shell
from harness.tools.base import Tool, ToolContext, ToolError, ToolOutput

ALL_TOOLS: dict[str, Tool] = {
    tool.name: tool
    for module in (files, shell, network, knowledge)
    for tool in module.TOOLS
}


def enabled_tools(settings: Settings) -> dict[str, Tool]:
    """Select the tools that the settings switch on.

    Args:
        settings: The validated settings.

    Returns:
        The enabled tools by name.

    Raises:
        ValueError: If ``tools.enabled`` lists a tool that does not exist.
    """
    unknown = set(settings.tools.enabled) - set(ALL_TOOLS)
    if unknown:
        raise ValueError(f"tools.enabled lists unknown tools: {sorted(unknown)}")
    return {name: ALL_TOOLS[name] for name in settings.tools.enabled}


__all__ = ["ALL_TOOLS", "enabled_tools", "Tool", "ToolContext", "ToolError", "ToolOutput"]
