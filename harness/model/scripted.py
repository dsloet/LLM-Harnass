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
    def __init__(self, scenario_path: Path) -> None:
        data = yaml.safe_load(Path(scenario_path).read_text(encoding="utf-8"))
        self.name = f"scripted:{Path(scenario_path).stem}"
        self._replies = list(_expand(data.get("steps") or []))
        self._position = 0

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        if self._position >= len(self._replies):
            return ModelReply(text="Scenario finished.")
        reply = self._replies[self._position]
        self._position += 1
        return reply


def _expand(steps: list[dict]):
    for step in steps:
        if "say" in step:
            yield ModelReply(text=str(step["say"]))
            continue
        call = ToolCall(name=str(step["tool"]), arguments=dict(step.get("args") or {}))
        for _ in range(int(step.get("repeat", 1))):
            yield ModelReply(text="", tool_calls=(call,))
