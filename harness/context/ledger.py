"""Provenance for everything the model sees.

Every piece of context becomes a ContextItem with a source ID, a trust level,
a version and a content hash. The ledger keeps all items of one session, so
that for every model call we can write a manifest: exactly which items, from
where, in which version, were in front of the model.

This answers the audit question "what did the model see?" completely.
"What did it use?" can only be narrowed down: see citations.py.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ContextItem:
    source_id: str          # e.g. "records:rec-001", "inbox:msg-001", "tool:read_file:2"
    trust: str              # owner | user | verified | untrusted
    kind: str               # rules | request | record | document | tool_output
    content: str
    version: str = ""
    retrieved_at: str = field(default_factory=now_iso)

    @property
    def sha256(self) -> str:
        return sha256_text(self.content)

    def manifest_entry(self) -> dict:
        """What goes in the audit log. The content itself is stored separately."""
        return {
            "source_id": self.source_id,
            "trust": self.trust,
            "kind": self.kind,
            "version": self.version,
            "sha256": self.sha256,
            "retrieved_at": self.retrieved_at,
            "chars": len(self.content),
        }


class ContextLedger:
    def __init__(self, trust_labels: bool) -> None:
        self.trust_labels = trust_labels
        self._items: dict[str, ContextItem] = {}

    def add(self, item: ContextItem) -> ContextItem:
        self._items[item.source_id] = item
        return item

    def has(self, source_id: str) -> bool:
        return source_id in self._items

    def manifest(self) -> list[dict]:
        return [item.manifest_entry() for item in self._items.values()]

    def render(self, item: ContextItem) -> str:
        """Text the model receives for one item.

        With trust labels on, data is wrapped so the model (and anyone reading
        the prompt later) can tell instructions from data. Labels do not make
        a model immune to injection; they make the boundary explicit and
        auditable. Switch them off in harness.yaml to compare.
        """
        if not self.trust_labels or item.trust in {"owner", "user"}:
            return item.content
        return (
            f'<data source="{item.source_id}" trust="{item.trust}" version="{item.version}">\n'
            f"{item.content}\n</data>"
        )
