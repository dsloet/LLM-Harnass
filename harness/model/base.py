"""What the harness needs from a model, and nothing more.

The model receives messages and tool descriptions, and returns text and/or
tool calls. It never executes anything itself: a ToolCall is only a proposal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    """A tool call the model PROPOSES. The policy gate decides if it runs."""

    name: str
    arguments: dict


@dataclass(frozen=True)
class ModelReply:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    raw: dict = field(default_factory=dict)


class ModelClient(Protocol):
    name: str

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        """Send the conversation and the available tools; get the next reply."""
        ...
