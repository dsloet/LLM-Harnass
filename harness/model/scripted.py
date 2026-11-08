"""A fake model that replays a scenario file.

Why? Real models are random and slow. To study the HARNESS, we want the same
model behaviour every run, including deliberately bad behaviour (a hijacked
model, a model stuck in a loop). Lessons and tests use this client.

Scenario format (see scenarios/*.yaml):

    steps:
      - tool: read_file            # propose a tool call
        args: {path: notes.txt}
        repeat: 3                  # optional: propose it 3 times
      - say: "Final answer"        # a final answer ends the session
"""
from __future__ import annotations

from pathlib import Path

import yaml

from harness.model.base import ModelReply, ToolCall


class ScriptedModel:
    """A model that returns the replies of a scenario file, one per call."""

    def __init__(self, scenario_path: Path) -> None:
        """Load the scenario.

        Args:
            scenario_path: Location of the scenario YAML file.
        """
        data = yaml.safe_load(Path(scenario_path).read_text(encoding="utf-8"))
        self.name = f"scripted:{Path(scenario_path).stem}"
        self._replies = list(_expand(data.get("steps") or []))
        self._position = 0

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        """Return the next scripted reply.

        Args:
            messages: The conversation so far. Not used: the script does not react to it.
            tools: The tool descriptions. Not used.

        Returns:
            The next reply, or a plain "Scenario finished." when the script is used up.
        """
        if self._position >= len(self._replies):
            return ModelReply(text="Scenario finished.")
        reply = self._replies[self._position]
        self._position += 1
        return reply


def _expand(steps: list[dict]):
    """Turn scenario steps into replies, repeating steps that ask for it.

    Args:
        steps: The ``steps`` list of the scenario.

    Yields:
        One ModelReply per proposed tool call or final answer.
    """
    for step in steps:
        if "say" in step:
            yield ModelReply(text=str(step["say"]))
            continue
        call = ToolCall(name=str(step["tool"]), arguments=dict(step.get("args") or {}))
        for _ in range(int(step.get("repeat", 1))):
            yield ModelReply(text="", tool_calls=(call,))
