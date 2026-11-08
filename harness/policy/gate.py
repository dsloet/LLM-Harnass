"""The policy gate: the only path from a proposed tool call to an action.

Design choices worth discussing in class:

* Fail closed. If no rule matches, the ``default`` applies, and the default
  shipped in config/policy.yaml is ``deny``. A gate that allows unknown
  actions protects only against the attacks you already thought of.
* Structured rules, not text patterns. Rules look at the tool name and parsed
  arguments (``argv[0]``, a path, a host), never at a raw command string.
  A regex over ``"ls && rm -rf data/"`` is easy to fool; ``argv[0] == "ls"``
  on an argument list that is never given to a shell is not.
* Fixed precedence: deny beats ask beats allow, whatever the order in the file.
* Validated at start-up: an unknown action or condition stops the harness.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from urllib.parse import urlparse

from harness.model.base import ToolCall


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    rule_id: str
    reason: str


@dataclass(frozen=True)
class Rule:
    id: str
    action: Decision
    tools: frozenset[str]
    when: dict
    reason: str


class PolicyError(ValueError):
    """The policy file is invalid. The harness refuses to start."""


_CONDITIONS = {"argv0_in", "path_glob", "url_domain_in"}
_PRECEDENCE = (Decision.DENY, Decision.ASK, Decision.ALLOW)


class PolicyGate:
    def __init__(self, policy: dict) -> None:
        self.default = _parse_decision(policy.get("default"), "default")
        self.rules = tuple(_parse_rule(raw) for raw in policy.get("rules") or [])

    def evaluate(self, call: ToolCall) -> Verdict:
        for action in _PRECEDENCE:
            for rule in self.rules:
                if rule.action is action and _matches(rule, call):
                    return Verdict(action, rule.id, rule.reason)
        return Verdict(self.default, "default", "No rule matched this call.")


def _parse_decision(value: object, where: str) -> Decision:
    try:
        return Decision(str(value))
    except ValueError:
        raise PolicyError(f"{where}: action must be allow, deny or ask, got {value!r}") from None


def _parse_rule(raw: dict) -> Rule:
    rule_id = raw.get("id") or "<missing id>"
    when = raw.get("when") or {}
    unknown = set(when) - _CONDITIONS
    if unknown:
        raise PolicyError(f"rule {rule_id}: unknown condition(s) {sorted(unknown)}")
    tools = raw.get("tool")
    if not tools:
        raise PolicyError(f"rule {rule_id}: 'tool' is required")
    tool_set = frozenset([tools] if isinstance(tools, str) else tools)
    return Rule(
        id=rule_id,
        action=_parse_decision(raw.get("action"), f"rule {rule_id}"),
        tools=tool_set,
        when=dict(when),
        reason=str(raw.get("reason", "")),
    )


def _matches(rule: Rule, call: ToolCall) -> bool:
    if call.name not in rule.tools:
        return False
    checks = {
        "argv0_in": _argv0_in,
        "path_glob": _path_glob,
        "url_domain_in": _url_domain_in,
    }
    return all(checks[name](call.arguments, expected) for name, expected in rule.when.items())


def _argv0_in(arguments: dict, allowed: list[str]) -> bool:
    argv = arguments.get("argv")
    if not isinstance(argv, list) or not argv:
        return False
    # "/bin/rm" and "rm" are the same program.
    return PurePosixPath(str(argv[0])).name in allowed


def _path_glob(arguments: dict, patterns: list[str]) -> bool:
    path = str(arguments.get("path", ""))
    normalised = str(PurePosixPath(path))
    return any(fnmatch.fnmatch(normalised, pattern) for pattern in patterns)


def _url_domain_in(arguments: dict, domains: list[str]) -> bool:
    host = urlparse(str(arguments.get("url", ""))).hostname or ""
    return host in domains
