"""One proposed tool call, through every control, in a fixed order.

    proposed -> known tool? -> policy gate -> (person approves?) -> pre hooks
             -> run the tool -> post hooks -> provenance + audit -> back to model

Every step writes an audit event, so the log shows not only what ran but
also what was refused, by which rule, and who approved what.
"""
from __future__ import annotations

import logging

from harness import console
from harness.context.ledger import ContextItem, sha256_text
from harness.model.base import ToolCall
from harness.policy.gate import Decision
from harness.session import Session
from harness.telemetry import span
from harness.tools.base import ToolContext, ToolError, ToolOutput

logger = logging.getLogger(__name__)


def handle_tool_call(session: Session, call: ToolCall) -> str:
    session.tool_calls += 1
    number = session.tool_calls
    console.proposal(number, call.name, call.arguments)
    session.audit.append("tool_proposed", {"n": number, "tool": call.name, "args": call.arguments})
    with span(session.tracer, f"tool {call.name}", tool=call.name, call_number=number) as current:
        refusal = _check(session, call, number)
        if refusal:
            current.set_attribute("outcome", "refused")
            return refusal
        content = _execute(session, call, number)
        current.set_attribute("outcome", "executed")
        return content


def _check(session: Session, call: ToolCall, number: int) -> str | None:
    """Return a refusal message for the model, or None if the call may run."""
    if call.name not in session.tools:
        session.audit.append("tool_refused", {"n": number, "reason": "unknown or disabled tool"})
        console.decision("deny", "-", "Unknown or disabled tool.")
        return f"Refused: there is no enabled tool called '{call.name}'."

    with span(session.tracer, "policy check", tool=call.name) as current:
        verdict = session.gate.evaluate(call)
        current.set_attribute("decision", verdict.decision.value)
        current.set_attribute("rule", verdict.rule_id)
    console.decision(verdict.decision.value, verdict.rule_id, verdict.reason)
    session.audit.append("policy_decision", {
        "n": number, "decision": verdict.decision.value, "rule": verdict.rule_id, "reason": verdict.reason,
    })
    if verdict.decision is Decision.DENY:
        return f"Refused by policy rule '{verdict.rule_id}': {verdict.reason}"
    if verdict.decision is Decision.ASK:
        result = session.approver.decide(call, verdict)
        session.audit.append("approval", {"n": number, "approved": result.approved, "approver": result.approver})
        console.note(f"approval: {'granted' if result.approved else 'refused'} by {result.approver}")
        if not result.approved:
            return f"Refused: a person did not approve this action ({verdict.reason})."

    pre = session.hooks.before(call)
    _log_events(session, pre.events)
    if pre.blocked:
        session.audit.append("hook_blocked", {"n": number, "reason": pre.reason})
        console.decision("deny", "hook", pre.reason)
        return f"Refused by a safety check: {pre.reason}"
    return None


def _execute(session: Session, call: ToolCall, number: int) -> str:
    ctx = ToolContext(
        settings=session.settings, catalog=session.catalog, user=session.user,
        role=session.role, session_id=session.audit.session_id, call_number=number,
    )
    try:
        output = session.tools[call.name].run(call.arguments, ctx)
    except ToolError as exc:
        session.audit.append("tool_error", {"n": number, "error": str(exc)})
        console.note(f"tool refused: {exc}")
        return f"Tool error: {exc}"
    except Exception as exc:  # noqa: BLE001 - logged with context, model gets a safe message
        logger.exception("Tool %s crashed", call.name)
        session.audit.append("tool_crash", {"n": number, "error": repr(exc)})
        return "Tool error: the tool failed unexpectedly. The failure was logged."
    finally:
        _log_events(session, ctx.events)
    return _record_output(session, call, number, output)


def _record_output(session: Session, call: ToolCall, number: int, output: ToolOutput) -> str:
    items = output.items or (ContextItem(
        source_id=f"tool:{call.name}:{number}",
        trust=session.catalog.tool_output_trust,
        kind="tool_output",
        content=output.text,
    ),)
    rendered, flags = [], {}
    for item in items:
        cleaned = _clean(session, call, item, flags)
        session.ledger.add(cleaned)
        rendered.append(session.ledger.render(cleaned))
    header = f"{output.text}\n\n" if output.items else ""
    content = header + "\n\n".join(rendered)
    session.audit.append("tool_result", {
        "n": number, "tool": call.name, "sources": [i.source_id for i in items],
        "chars": len(content), "sha256": sha256_text(content), "flags": flags,
    })
    console.note(f"result: {len(content)} chars from {', '.join(i.source_id for i in items)}")
    for key, value in flags.items():
        console.say(f"    flag: {key} {value}", "ask")
    return content


def _clean(session: Session, call: ToolCall, item: ContextItem, flags: dict) -> ContextItem:
    """Truncate long output and run post hooks. The model sees the cleaned text."""
    limit = session.settings.limits.max_output_chars
    text = item.content
    if len(text) > limit:
        flags["truncated"] = {"original_chars": len(text), "original_sha256": sha256_text(text)}
        text = text[:limit] + f"\n[... cut at {limit} characters]"
    post = session.hooks.after(call, text, item.trust)
    _log_events(session, post.events)
    flags.update(post.flags)
    return ContextItem(item.source_id, item.trust, item.kind, post.text, item.version, item.retrieved_at)


def _log_events(session: Session, events: list[tuple[str, dict]]) -> None:
    for event, data in events:
        session.audit.append(event, data)
