"""Human approval for calls the policy marks as "ask".

Modes (config: approval.mode, or --approval on the command line):
    prompt   ask the person at the terminal
    deny     refuse every "ask" (unattended runs)
    approve  allow every "ask" (ONLY for tests; never in real use)

Fail closed: in prompt mode without a terminal, nobody can answer, so the
answer is no.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass

from harness.model.base import ToolCall
from harness.policy.gate import Verdict


@dataclass(frozen=True)
class ApprovalResult:
    approved: bool
    approver: str


class Approver:
    def __init__(self, mode: str, user: str) -> None:
        self.mode = mode
        self.user = user

    def decide(self, call: ToolCall, verdict: Verdict) -> ApprovalResult:
        if self.mode == "approve":
            return ApprovalResult(True, "auto-approve (test mode)")
        if self.mode == "deny" or not sys.stdin.isatty():
            return ApprovalResult(False, f"auto-deny ({self.mode} mode)")
        return self._prompt(call, verdict)

    def _prompt(self, call: ToolCall, verdict: Verdict) -> ApprovalResult:
        print("\n  APPROVAL NEEDED")
        print(f"  tool:   {call.name}")
        print(f"  args:   {json.dumps(call.arguments, ensure_ascii=False)[:400]}")
        print(f"  why:    {verdict.reason} (rule {verdict.rule_id})")
        try:
            answer = input("  Allow this action? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        return ApprovalResult(answer in {"y", "yes"}, self.user)
