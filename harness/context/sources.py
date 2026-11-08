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
    items: tuple[ContextItem, ...]
    withheld: tuple[str, ...]          # IDs the user may not see; logged, never shown


class SourceCatalog:
    def __init__(self, settings: Settings) -> None:
        catalog = load_yaml(settings.paths.config_dir / "sources.yaml")
        self._sources = catalog["sources"]
        self.tool_output_trust = catalog.get("tool_output_trust", "untrusted")
        self._config_dir = settings.paths.config_dir
        self._data_dir = settings.paths.data_dir

    def system_rules(self) -> ContextItem:
        source = self._sources["system-rules"]
        path = self._config_dir / source["path"]
        text = path.read_text(encoding="utf-8")
        return ContextItem("system-rules", source["trust"], "rules", text, version=_mtime(path))

    def search_records(self, query: str, role: str) -> SearchResult:
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
        records = []
        for path in sorted(folder.glob("*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError as exc:
                logger.error("Skipping unreadable source file %s: %s", path, exc)
        return records


def _matches(record: dict, query: str) -> bool:
    haystack = f"{record.get('title', '')} {record.get('content', '')}".lower()
    return all(word in haystack for word in query.lower().split())


def _mtime(path: Path) -> str:
    return str(int(path.stat().st_mtime))
