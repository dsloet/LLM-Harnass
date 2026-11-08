"""Built-in hooks. Enable them in harness.yaml under hooks.enabled.

pre hooks run before a tool call and may block it.
post hooks run on the tool's output and may change it or raise a flag.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from harness.model.base import ToolCall


@dataclass(frozen=True)
class PostResult:
    """The result of a post hook.

    Attributes:
        text: The text after the hook ran.
        flags: Warnings for the audit log. Empty if there is nothing to report.
    """

    text: str
    flags: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Hook:
    """A named hook.

    Attributes:
        name: Name used in ``hooks.enabled``.
        stage: ``pre`` runs before the tool, ``post`` runs on its output.
        fn: The function to call.
    """

    name: str
    stage: str                    # "pre" or "post"
    fn: Callable


# ---------- secret_redactor (post) ----------
# Report risk 8: the model must not see (or repeat) secrets that a tool returns.
_SECRET_PATTERNS = {
    "api_key": re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_\-]{16,}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    # Matches API_TOKEN=..., db_password: ..., secret = ...
    "assignment": re.compile(r"(?i)\b\w*(password|passwd|secret|token|api_key)\s*[=:]\s*\S+"),
}


def secret_redactor(call: ToolCall, text: str, trust: str) -> PostResult:
    """Replace secrets in the output with a marker.

    Args:
        call: The tool call that produced the text. Not used.
        text: The tool output.
        trust: Trust level of the output. Not used.

    Returns:
        The cleaned text and a flag that counts the redactions per kind.
    """
    found = {}
    for label, pattern in _SECRET_PATTERNS.items():
        text, count = pattern.subn(f"[REDACTED:{label}]", text)
        if count:
            found[label] = count
    return PostResult(text, {"secrets_redacted": found} if found else {})


# ---------- injection_flagger (post) ----------
# Report risk 6. Detection by phrases is weak: an attacker rephrases. This hook
# FLAGS for the audit trail and the person reviewing; it is not the defence.
# The defence is that a hijacked model still cannot do anything dangerous.
_INJECTION_HINTS = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior) instructions|do not (tell|mention)"
    r"|system prompt|you are now|<!--.*?(assistant|ai)\s*:)"
)


def injection_flagger(call: ToolCall, text: str, trust: str) -> PostResult:
    """Flag phrases that look like a prompt injection in untrusted output.

    Args:
        call: The tool call that produced the text. Not used.
        text: The tool output. It is not changed.
        trust: Trust level of the output. Only ``untrusted`` output is checked.

    Returns:
        The unchanged text and a flag that lists the phrases found.
    """
    if trust != "untrusted":
        return PostResult(text)
    hits = sorted({m.group(0)[:60] for m in _INJECTION_HINTS.finditer(text)})
    return PostResult(text, {"possible_injection": hits} if hits else {})


# ---------- always_crashes (pre) ----------
# Lesson 2: enable this hook and compare hooks.fail_closed true vs false.
def always_crashes(call: ToolCall) -> str | None:
    """Fail on purpose, to show what a crashing hook does.

    Args:
        call: The tool call. Not used.

    Raises:
        RuntimeError: Always.
    """
    raise RuntimeError("this hook is broken on purpose")


BUILTIN_HOOKS = {
    "secret_redactor": Hook("secret_redactor", "post", secret_redactor),
    "injection_flagger": Hook("injection_flagger", "post", injection_flagger),
    "always_crashes": Hook("always_crashes", "pre", always_crashes),
}
