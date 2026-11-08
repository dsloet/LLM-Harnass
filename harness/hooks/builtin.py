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
    text: str
    flags: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Hook:
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
    if trust != "untrusted":
        return PostResult(text)
    hits = sorted({m.group(0)[:60] for m in _INJECTION_HINTS.finditer(text)})
    return PostResult(text, {"possible_injection": hits} if hits else {})


# ---------- always_crashes (pre) ----------
# Lesson 2: enable this hook and compare hooks.fail_closed true vs false.
def always_crashes(call: ToolCall) -> str | None:
    raise RuntimeError("this hook is broken on purpose")


BUILTIN_HOOKS = {
    "secret_redactor": Hook("secret_redactor", "post", secret_redactor),
    "injection_flagger": Hook("injection_flagger", "post", injection_flagger),
    "always_crashes": Hook("always_crashes", "pre", always_crashes),
}
