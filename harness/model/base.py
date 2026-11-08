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
    """One reply from the model.

    Attributes:
        text: The text of the reply. For a final answer this is the answer.
        tool_calls: The tool calls the model proposes, possibly none.
        raw: The unprocessed response, kept for debugging.
    """

    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    raw: dict = field(default_factory=dict)


class ModelClient(Protocol):
    """What every model client must offer.

    Attributes:
        name: Name used in the audit log, for example ``ollama:qwen``.
    """

    name: str

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        """Send the conversation and the available tools; get the next reply.

        Args:
            messages: The conversation so far.
            tools: The tool descriptions the model may use.

        Returns:
            The model's reply.
        """
        ...
