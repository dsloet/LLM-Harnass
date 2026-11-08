"""Everything one agent session needs, built once from the configuration."""
from __future__ import annotations

from dataclasses import dataclass

from opentelemetry import trace

from harness.audit.log import AuditLog
from harness.config import Settings, load_yaml
from harness.context.ledger import ContextLedger
from harness.context.sources import SourceCatalog
from harness.hooks.runner import HookRunner
from harness.model.base import ModelClient
from harness.policy.approval import Approver
from harness.policy.gate import PolicyGate
from harness.tools import Tool, enabled_tools


@dataclass
class Session:
    settings: Settings
    model: ModelClient
    audit: AuditLog
    ledger: ContextLedger
    catalog: SourceCatalog
    gate: PolicyGate
    approver: Approver
    hooks: HookRunner
    tools: dict[str, Tool]
    tracer: trace.Tracer
    user: str
    role: str
    tool_calls: int = 0


def build_session(settings: Settings, model: ModelClient, tracer: trace.Tracer,
                  user: str, role: str) -> Session:
    """Wire the components together. Any invalid config fails here, before any action."""
    policy = load_yaml(settings.paths.config_dir / "policy.yaml")
    return Session(
        settings=settings,
        model=model,
        audit=AuditLog(settings.paths.audit_dir),
        ledger=ContextLedger(settings.context.trust_labels),
        catalog=SourceCatalog(settings),
        gate=PolicyGate(policy),
        approver=Approver(settings.approval.mode, user),
        hooks=HookRunner(settings.hooks),
        tools=enabled_tools(settings),
        tracer=tracer,
        user=user,
        role=role,
    )
