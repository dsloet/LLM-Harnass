"""Shared types for tools.

A tool is the ONLY way the model affects anything. Each tool:
  * has a JSON schema the model sees (what it can ask for),
  * checks its own arguments again, even after the policy gate allowed the call
    (defence in depth: a policy mistake should not be enough to cause damage),
  * returns text plus, optionally, context items with their provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from harness.config import Settings
from harness.context.ledger import ContextItem
from harness.context.sources import SourceCatalog


class ToolError(Exception):
    """A tool refused or failed. The message is shown to the model and logged."""


@dataclass
class ToolContext:
    """What a tool may know about the current call.

    Attributes:
        settings: The validated settings.
        catalog: The source catalog, for tools that read company data.
        user: Name of the person who started the run.
        role: Role of that person.
        session_id: ID of the session.
        call_number: Running number of the call in this session.
        events: Extra audit events the tool wants written.
    """

    settings: Settings
    catalog: SourceCatalog
    user: str
    role: str
    session_id: str
    call_number: int = 0
    events: list[tuple[str, dict]] = field(default_factory=list)  # extra audit events

    def note(self, event: str, data: dict) -> None:
        """Let a tool add an audit event (for example: records withheld).

        Args:
            event: Name of the event.
            data: The details of the event.
        """
        self.events.append((event, data))


@dataclass(frozen=True)
class ToolOutput:
    """What a tool returns.

    Attributes:
        text: A short text for the model.
        items: Context items with provenance. If empty, the text becomes one tool_output item.
    """

    text: str
    items: tuple[ContextItem, ...] = ()   # if empty, the text becomes one tool_output item


@dataclass(frozen=True)
class Tool:
    """A tool the model can propose to use.

    Attributes:
        name: Name the model uses to call the tool.
        description: What the tool does, shown to the model.
        parameters: JSON schema of the arguments.
        run: Function that does the work. It takes the arguments and a ToolContext.
    """

    name: str
    description: str
    parameters: dict
    run: Callable[[dict, ToolContext], ToolOutput]

    def schema(self) -> dict:
        """Describe the tool in the format model servers expect.

        Returns:
            A function description with name, description and parameters.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def require_str(arguments: dict, key: str) -> str:
    """Get a non-empty string argument.

    Args:
        arguments: The arguments the model gave.
        key: Name of the argument.

    Returns:
        The value.

    Raises:
        ToolError: If the argument is missing, empty or not a string.
    """
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ToolError(f"Argument '{key}' must be a non-empty string.")
    return value


def confine(workspace: Path, relative: str) -> Path:
    """Resolve a path and refuse anything outside the workspace.

    Catches "../../etc/passwd", absolute paths and symlinks that point out.

    Args:
        workspace: The workspace folder.
        relative: The path the model asked for, relative to the workspace.

    Returns:
        The resolved absolute path.

    Raises:
        ToolError: If the path leads outside the workspace.
    """
    root = workspace.resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ToolError(f"Path '{relative}' is outside the workspace.")
    return target
