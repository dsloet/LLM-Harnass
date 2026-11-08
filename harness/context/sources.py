"""Read-only context sources: system rules, internal records and the inbox.

The access filter runs HERE, before a record can enter the context. Filtering
after the model has seen a record is too late: the model can repeat it.
(Report risk 22: access leakage through retrieval.)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from harness.config import Settings, load_yaml
from harness.context.ledger import ContextItem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """The outcome of a record search.

    Attributes:
        items: Records the user may see.
        withheld: IDs of matching records the user may not see. Logged, never shown.
    """

    items: tuple[ContextItem, ...]
    withheld: tuple[str, ...]          # IDs the user may not see; logged, never shown


class SourceCatalog:
    """Reads the configured sources and applies the access filter."""

    def __init__(self, settings: Settings) -> None:
        """Load the source catalog.

        Args:
            settings: The validated settings, for the config and data folders.
        """
        catalog = load_yaml(settings.paths.config_dir / "sources.yaml")
        self._sources = catalog["sources"]
        self.tool_output_trust = catalog.get("tool_output_trust", "untrusted")
        self._config_dir = settings.paths.config_dir
        self._data_dir = settings.paths.data_dir

    def system_rules(self) -> ContextItem:
        """Read the system rules.

        Returns:
            The rules as a context item, versioned by file modification time.
        """
        source = self._sources["system-rules"]
        path = self._config_dir / source["path"]
        text = path.read_text(encoding="utf-8")
        return ContextItem("system-rules", source["trust"], "rules", text, version=_mtime(path))

    def search_records(self, query: str, role: str) -> SearchResult:
        """Find records that match every word of the query and that the role may see.

        Args:
            query: Search words.
            role: Role of the user, checked against ``allowed_roles`` of each record.

        Returns:
            The visible records and the IDs that were withheld.
        """
        source = self._sources["records"]
        visible, withheld = [], []
        for record in self._read_json_dir(self._data_dir / source["path"]):
            if not _matches(record, query):
                continue
            if role not in record.get("allowed_roles", []):
                withheld.append(record["id"])
                continue
            visible.append(ContextItem(
                source_id=f"records:{record['id']}",
                trust=source["trust"],
                kind="record",
                content=f"{record['title']}\n{record['content']}",
                version=f"v{record.get('version', '?')} ({record.get('updated_at', '?')})",
            ))
        return SearchResult(tuple(visible), tuple(withheld))

    def inbox(self) -> tuple[ContextItem, ...]:
        """Read all messages of the inbox.

        Returns:
            One item per message. Their trust level comes from the catalog.
        """
        source = self._sources["inbox"]
        items = []
        for message in self._read_json_dir(self._data_dir / source["path"]):
            content = (
                f"From: {message['from']}\nSubject: {message['subject']}\n\n{message['body']}"
            )
            items.append(ContextItem(
                source_id=f"inbox:{message['id']}",
                trust=source["trust"],
                kind="document",
                content=content,
                version=message.get("received_at", ""),
            ))
        return tuple(items)

    @staticmethod
    def _read_json_dir(folder: Path) -> list[dict]:
        """Read every JSON file of a folder, skipping files that are not valid JSON.

        Args:
            folder: The folder to read.

        Returns:
            The parsed files, sorted by file name.
        """
        records = []
        for path in sorted(folder.glob("*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError as exc:
                logger.error("Skipping unreadable source file %s: %s", path, exc)
        return records


def _matches(record: dict, query: str) -> bool:
    """Check that every word of the query occurs in the title or content.

    Args:
        record: The record to test.
        query: Search words.

    Returns:
        True if all words are found, ignoring case.
    """
    haystack = f"{record.get('title', '')} {record.get('content', '')}".lower()
    return all(word in haystack for word in query.lower().split())


def _mtime(path: Path) -> str:
    """Return the modification time of a file as a whole number of seconds, as text.

    Args:
        path: The file to look at.

    Returns:
        The time as a string, used as a version.
    """
    return str(int(path.stat().st_mtime))
