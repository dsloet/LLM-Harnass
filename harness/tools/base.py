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
    settings: Settings
    catalog: SourceCatalog
    user: str
    role: str
    session_id: str
    call_number: int = 0
    events: list[tuple[str, dict]] = field(default_factory=list)  # extra audit events

    def note(self, event: str, data: dict) -> None:
        """Let a tool add an audit event (for example: records withheld)."""
        self.events.append((event, data))


@dataclass(frozen=True)
class ToolOutput:
    text: str
    items: tuple[ContextItem, ...] = ()   # if empty, the text becomes one tool_output item


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    run: Callable[[dict, ToolContext], ToolOutput]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def require_str(arguments: dict, key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ToolError(f"Argument '{key}' must be a non-empty string.")
    return value


def confine(workspace: Path, relative: str) -> Path:
    """Resolve a path and refuse anything outside the workspace.

    Catches "../../etc/passwd", absolute paths and symlinks that point out.
    """
    root = workspace.resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ToolError(f"Path '{relative}' is outside the workspace.")
    return target
