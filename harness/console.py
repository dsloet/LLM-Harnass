"""Terminal output for the CLI. Kept apart so the loop stays readable."""
from __future__ import annotations

import json
import sys

_COLOURS = {"allow": "32", "deny": "31", "ask": "33", "info": "36", "dim": "2", "bold": "1"}


def _paint(text: str, colour: str) -> str:
    """Wrap text in a colour code, but only when writing to a terminal.

    Args:
        text: The text to colour.
        colour: A key of ``_COLOURS``.

    Returns:
        The coloured text, or the plain text when output is piped.
    """
    if not sys.stdout.isatty():
        return text
    return f"\033[{_COLOURS[colour]}m{text}\033[0m"


def say(text: str, colour: str = "info") -> None:
    """Print one line.

    Args:
        text: The line to print.
        colour: A key of ``_COLOURS``.
    """
    print(_paint(text, colour), flush=True)


def proposal(number: int, tool: str, arguments: dict) -> None:
    """Show a tool call the model proposes.

    Args:
        number: Running number of the call in this session.
        tool: Name of the tool.
        arguments: The arguments the model gave. Long output is cut at 200 characters.
    """
    args = json.dumps(arguments, ensure_ascii=False)
    say(f"\n[{number}] model proposes {tool} {args[:200]}", "bold")


def decision(kind: str, rule: str, reason: str) -> None:
    """Show the policy decision for a call.

    Args:
        kind: ``allow``, ``deny`` or ``ask``. It also picks the colour.
        rule: ID of the rule that decided.
        reason: Why the rule decided this way.
    """
    say(f"    policy: {kind.upper()} (rule {rule}) {reason}", kind)


def note(text: str) -> None:
    """Print a dimmed, indented line of extra detail.

    Args:
        text: The text to print.
    """
    say(f"    {text}", "dim")
