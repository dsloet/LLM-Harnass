"""Run hooks, and decide what a crashing hook means.

hooks.fail_closed = true   a crashing pre hook BLOCKS the call; a crashing
                           post hook WITHHOLDS the output.
hooks.fail_closed = false  the crash is logged and the call goes ahead.

The second mode is how many home-made harnesses behave by accident: the
security check throws, someone catches and prints the error, and the action
it was meant to stop runs anyway. Lesson 2 lets you see both.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from harness.config import HookSettings
from harness.hooks.builtin import BUILTIN_HOOKS, Hook, PostResult
from harness.model.base import ToolCall

logger = logging.getLogger(__name__)


@dataclass
class PreOutcome:
    """The result of all pre hooks.

    Attributes:
        blocked: True if the call must not run.
        reason: Why it was blocked.
        events: Audit events written by the hooks, as pairs of name and data.
    """

    blocked: bool = False
    reason: str = ""
    events: list[tuple[str, dict]] = field(default_factory=list)


@dataclass
class PostOutcome:
    """The result of all post hooks.

    Attributes:
        text: The output after all hooks ran.
        flags: Warnings collected from the hooks.
        events: Audit events written by the hooks, as pairs of name and data.
    """

    text: str
    flags: dict = field(default_factory=dict)
    events: list[tuple[str, dict]] = field(default_factory=list)


class HookRunner:
    """Runs the enabled hooks around a tool call."""

    def __init__(self, settings: HookSettings) -> None:
        """Select the enabled hooks.

        Args:
            settings: The hook settings.

        Raises:
            ValueError: If an enabled hook does not exist.
        """
        unknown = set(settings.enabled) - set(BUILTIN_HOOKS)
        if unknown:
            raise ValueError(f"hooks.enabled lists unknown hooks: {sorted(unknown)}")
        self.fail_closed = settings.fail_closed
        hooks = [BUILTIN_HOOKS[name] for name in settings.enabled]
        self._pre = [h for h in hooks if h.stage == "pre"]
        self._post = [h for h in hooks if h.stage == "post"]

    def before(self, call: ToolCall) -> PreOutcome:
        """Run the pre hooks. The first one that blocks stops the others.

        Args:
            call: The proposed tool call.

        Returns:
            The outcome. A crashing hook blocks the call when ``fail_closed`` is set.
        """
        outcome = PreOutcome()
        for hook in self._pre:
            try:
                reason = hook.fn(call)
            except Exception as exc:  # noqa: BLE001 - the point is to decide what a crash means
                self._record_crash(outcome.events, hook, exc)
                if self.fail_closed:
                    return PreOutcome(True, f"hook '{hook.name}' crashed (fail closed)", outcome.events)
                continue
            if reason:
                return PreOutcome(True, f"hook '{hook.name}': {reason}", outcome.events)
        return outcome

    def after(self, call: ToolCall, text: str, trust: str) -> PostOutcome:
        """Run the post hooks, each on the output of the one before.

        Args:
            call: The tool call that produced the text.
            text: The tool output.
            trust: Trust level of the output.

        Returns:
            The outcome. A crashing hook withholds the output when ``fail_closed`` is set.
        """
        outcome = PostOutcome(text)
        for hook in self._post:
            try:
                result: PostResult = hook.fn(call, outcome.text, trust)
            except Exception as exc:  # noqa: BLE001
                self._record_crash(outcome.events, hook, exc)
                if self.fail_closed:
                    return PostOutcome("[output withheld: a safety hook failed]",
                                       outcome.flags, outcome.events)
                continue
            outcome.text = result.text
            outcome.flags.update(result.flags)
        return outcome

    def _record_crash(self, events: list, hook: Hook, exc: Exception) -> None:
        """Log a crashing hook and add an audit event.

        Args:
            events: The event list of the current outcome. It is extended in place.
            hook: The hook that crashed.
            exc: The exception it raised.
        """
        logger.error("Hook %s crashed: %s", hook.name, exc)
        events.append(("hook_error", {"hook": hook.name, "error": str(exc), "fail_closed": self.fail_closed}))
