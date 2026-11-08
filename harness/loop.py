"""The agent loop.

    while steps and time remain:
        record exactly what the model will see   (context manifest + full prompt)
        ask the model for its next step
        no tool calls?  -> final answer: check citations, stop
        tool calls?     -> each one goes through dispatch.handle_tool_call
                           and its result is added to the conversation as DATA

The loop itself makes no decisions about safety. Those live in the policy
gate, the tools, the hooks and the container. That separation is the core
idea of a harness: the model proposes, the harness decides and records.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from harness import console
from harness.config import Settings, file_fingerprint
from harness.context.citations import CitationReport, check_citations
from harness.context.ledger import ContextItem
from harness.dispatch import handle_tool_call
from harness.model.base import ModelClient, ModelReply
from harness.model.ollama import ModelError
from harness.session import Session, build_session
from harness.telemetry import init_tracing, shutdown_tracing, span


@dataclass(frozen=True)
class SessionResult:
    session_id: str
    stop_reason: str                      # final_answer | step_limit | time_limit | model_error
    answer: str = ""
    citations: CitationReport | None = None


def run_session(settings: Settings, model: ModelClient, task: str, user: str, role: str) -> SessionResult:
    tracer = init_tracing(settings.telemetry)
    session = build_session(settings, model, tracer, user, role)
    _start(session, task)
    messages = _opening_messages(session, task)
    try:
        with span(tracer, "agent session", session=session.audit.session_id, user=user, role=role):
            result = _run(session, messages)
    finally:
        shutdown_tracing()
    session.audit.append("session_end", {"stop_reason": result.stop_reason, "tool_calls": session.tool_calls})
    console.say(f"\nSession {result.session_id} ended: {result.stop_reason}. "
                f"Audit log: {session.audit.path}", "info")
    return result


def _start(session: Session, task: str) -> None:
    paths = session.settings.paths
    session.audit.append("session_start", {
        "user": session.user,
        "role": session.role,
        "task": task,
        "model": session.model.name,
        "settings_fingerprint": session.settings.fingerprint(),
        "policy_fingerprint": file_fingerprint(paths.config_dir / "policy.yaml"),
        "approval_mode": session.settings.approval.mode,
        "tools": sorted(session.tools),
    })
    console.say(f"Session {session.audit.session_id} | model {session.model.name} | "
                f"user {session.user} ({session.role})", "bold")


def _opening_messages(session: Session, task: str) -> list[dict]:
    rules = session.ledger.add(session.catalog.system_rules())
    request = session.ledger.add(ContextItem("request", "user", "request", task))
    return [
        {"role": "system", "content": rules.content},
        {"role": "user", "content": request.content},
    ]


def _run(session: Session, messages: list[dict]) -> SessionResult:
    limits = session.settings.limits
    started = time.monotonic()
    session_id = session.audit.session_id
    for step in range(1, limits.max_steps + 1):
        if time.monotonic() - started > limits.max_seconds:
            return _stopped(session, "time_limit", f"more than {limits.max_seconds} seconds")
        try:
            reply = _call_model(session, messages, step)
        except ModelError as exc:
            session.audit.append("model_error", {"step": step, "error": str(exc)})
            console.say(f"Model error: {exc}", "deny")
            return SessionResult(session_id, "model_error")
        if not reply.tool_calls:
            return _finish(session, reply.text)
        messages.append(_assistant_message(reply))
        for call in reply.tool_calls:
            content = handle_tool_call(session, call)
            messages.append({"role": "tool", "content": content})
    return _stopped(session, "step_limit", f"{limits.max_steps} model calls")


def _call_model(session: Session, messages: list[dict], step: int) -> ModelReply:
    call_id = f"{session.audit.session_id}-{step:02d}"
    schemas = [tool.schema() for tool in session.tools.values()]
    manifest = session.ledger.manifest()
    prompt_hash = session.audit.store_call(call_id, {
        "model": session.model.name, "manifest": manifest, "messages": messages, "tools": schemas,
    })
    session.audit.append("model_call", {
        "call_id": call_id, "step": step, "prompt_sha256": prompt_hash, "manifest": manifest,
    })
    with span(session.tracer, "model call", call_id=call_id, step=step,
              context_items=len(manifest), model=session.model.name):
        reply = session.model.complete(messages, schemas)
    session.audit.append("model_reply", {
        "call_id": call_id,
        "text": reply.text[:1000],
        "tool_calls": [{"tool": c.name, "args": c.arguments} for c in reply.tool_calls],
    })
    return reply


def _assistant_message(reply: ModelReply) -> dict:
    return {
        "role": "assistant",
        "content": reply.text,
        "tool_calls": [{"function": {"name": c.name, "arguments": c.arguments}} for c in reply.tool_calls],
    }


def _finish(session: Session, answer: str) -> SessionResult:
    report = check_citations(answer, session.ledger, session.settings.context.require_citations)
    session.audit.append("final_answer", {
        "text": answer, "cited": list(report.cited), "unknown_citations": list(report.unknown),
        "citations_missing": report.missing, "citations_ok": report.ok,
    })
    console.say(f"\nAnswer:\n{answer}", "bold")
    if report.unknown:
        console.say(f"Citation check FAILED: never seen by the model: {', '.join(report.unknown)}", "deny")
    elif report.missing:
        console.say("Citation check FAILED: the answer cites no sources.", "deny")
    else:
        console.say(f"Citation check passed: {', '.join(report.cited) or 'no citations required'}", "allow")
    return SessionResult(session.audit.session_id, "final_answer", answer, report)


def _stopped(session: Session, reason: str, detail: str) -> SessionResult:
    session.audit.append("limit_reached", {"reason": reason, "detail": detail})
    console.say(f"\nStopped: {reason} ({detail}).", "deny")
    return SessionResult(session.audit.session_id, reason)
