"""Terminal output for the CLI. Kept apart so the loop stays readable."""
from __future__ import annotations

import json
import sys

_COLOURS = {"allow": "32", "deny": "31", "ask": "33", "info": "36", "dim": "2", "bold": "1"}


def _paint(text: str, colour: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{_COLOURS[colour]}m{text}\033[0m"


def say(text: str, colour: str = "info") -> None:
    print(_paint(text, colour), flush=True)


def proposal(number: int, tool: str, arguments: dict) -> None:
    args = json.dumps(arguments, ensure_ascii=False)
    say(f"\n[{number}] model proposes {tool} {args[:200]}", "bold")


def decision(kind: str, rule: str, reason: str) -> None:
    say(f"    policy: {kind.upper()} (rule {rule}) {reason}", kind)


def note(text: str) -> None:
    say(f"    {text}", "dim")
