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
    """Hash text with SHA-256.

    Args:
        text: The text to hash.

    Returns:
        The hash as hex text.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string, to the second."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ContextItem:
    """One piece of context with its source and trust level.

    Attributes:
        source_id: Where it came from, for example ``records:rec-001``.
        trust: ``owner``, ``user``, ``verified`` or ``untrusted``.
        kind: ``rules``, ``request``, ``record``, ``document`` or ``tool_output``.
        content: The text itself.
        version: Version or date of the source, if known.
        retrieved_at: When the item was read.
    """

    source_id: str          # e.g. "records:rec-001", "inbox:msg-001", "tool:read_file:2"
    trust: str              # owner | user | verified | untrusted
    kind: str               # rules | request | record | document | tool_output
    content: str
    version: str = ""
    retrieved_at: str = field(default_factory=now_iso)

    @property
    def sha256(self) -> str:
        """Return the SHA-256 hash of the content."""
        return sha256_text(self.content)

    def manifest_entry(self) -> dict:
        """What goes in the audit log. The content itself is stored separately.

        Returns:
            A dictionary with the source, trust, kind, version, hash, time and length.
        """
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
    """Keeps every item the model has seen in one session."""

    def __init__(self, trust_labels: bool) -> None:
        """Create an empty ledger.

        Args:
            trust_labels: If True, untrusted items are wrapped in a label when rendered.
        """
        self.trust_labels = trust_labels
        self._items: dict[str, ContextItem] = {}

    def add(self, item: ContextItem) -> ContextItem:
        """Store an item, replacing any earlier item with the same source ID.

        Args:
            item: The item to store.

        Returns:
            The same item, for convenience.
        """
        self._items[item.source_id] = item
        return item

    def has(self, source_id: str) -> bool:
        """Check whether the model has seen a source.

        Args:
            source_id: The source ID to look for.

        Returns:
            True if the ledger holds an item with that ID.
        """
        return source_id in self._items

    def manifest(self) -> list[dict]:
        """List the manifest entries of all items.

        Returns:
            One entry per item, in the order they were added.
        """
        return [item.manifest_entry() for item in self._items.values()]

    def render(self, item: ContextItem) -> str:
        """Text the model receives for one item.

        With trust labels on, data is wrapped so the model (and anyone reading
        the prompt later) can tell instructions from data. Labels do not make
        a model immune to injection; they make the boundary explicit and
        auditable. Switch them off in harness.yaml to compare.

        Args:
            item: The item to render.

        Returns:
            The plain content for owner and user items, or the labelled content.
        """
        if not self.trust_labels or item.trust in {"owner", "user"}:
            return item.content
        return (
            f'<data source="{item.source_id}" trust="{item.trust}" version="{item.version}">\n'
            f"{item.content}\n</data>"
        )
