"""A tamper-evident, append-only audit log.

Each line is one JSON event. Every event contains the hash of the previous
event, and its own hash covers its content plus that previous hash. Change,
delete or reorder one line and every hash after it stops matching:
``python -m harness verify-audit`` finds the first broken line.

Two properties to discuss in class:
* Tamper-EVIDENT, not tamper-proof. Someone with write access can rewrite the
  whole chain. In production, ship the chain head to a separate system
  (a write-once bucket, a SIEM) so a rewrite is detectable.
* Out of the agent's reach. The audit folder is mounted at /audit; the agent's
  file tools only work inside /workspace. The harness writes the log, the
  model cannot.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from harness.context.ledger import now_iso

GENESIS = "0" * 64
LOG_NAME = "audit.jsonl"


def _canonical(record: dict) -> bytes:
    """Serialise a record the same way every time, so its hash is stable.

    Args:
        record: The record to serialise.

    Returns:
        Compact JSON bytes with sorted keys.
    """
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _hash(record_without_hash: dict) -> str:
    """Hash a record that does not yet contain its own hash.

    Args:
        record_without_hash: The record without the ``hash`` field.

    Returns:
        The SHA-256 hash as hex text.
    """
    return hashlib.sha256(_canonical(record_without_hash)).hexdigest()


class AuditLog:
    """Append-only log file whose events are linked by hashes."""

    def __init__(self, audit_dir: Path, session_id: str | None = None) -> None:
        """Open the log, creating the folders if needed, and find the end of the chain.

        Args:
            audit_dir: Folder for the log file and the stored model calls.
            session_id: ID for this session. A random one is made if it is None.
        """
        self.dir = Path(audit_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "calls").mkdir(exist_ok=True)
        self.path = self.dir / LOG_NAME
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self._prev_hash, self._seq = self._tail()

    def append(self, event: str, data: dict) -> dict:
        """Add one event to the end of the chain.

        Args:
            event: Name of the event, for example ``tool_result``.
            data: The details of the event.

        Returns:
            The full record as written, including its hash.
        """
        record = {
            "seq": self._seq + 1,
            "ts": now_iso(),
            "session": self.session_id,
            "event": event,
            "data": data,
            "prev_hash": self._prev_hash,
        }
        record["hash"] = _hash(record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._prev_hash, self._seq = record["hash"], record["seq"]
        return record

    def store_call(self, call_id: str, payload: dict) -> str:
        """Store the full prompt of one model call; return its hash for the log.

        Args:
            call_id: ID of the model call. It becomes the file name.
            payload: The model name, manifest, messages and tool descriptions.

        Returns:
            The SHA-256 hash of the stored file content.
        """
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        (self.dir / "calls" / f"{call_id}.json").write_text(body, encoding="utf-8")
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _tail(self) -> tuple[str, int]:
        """Read the hash and sequence number of the last event in the log.

        Returns:
            The last hash and sequence number, or the genesis hash and 0 for an empty log.
        """
        if not self.path.exists():
            return GENESIS, 0
        last = None
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        if last is None:
            return GENESIS, 0
        record = json.loads(last)
        return record["hash"], record["seq"]


@dataclass(frozen=True)
class VerifyResult:
    """The outcome of checking the chain.

    Attributes:
        ok: True if the whole chain is intact.
        events: Number of intact events before the first problem.
        first_bad_line: Line number of the first broken event, or None.
        problem: Description of what is wrong, or a note when nothing is.
    """

    ok: bool
    events: int
    first_bad_line: int | None = None
    problem: str = ""


def verify_chain(path: Path) -> VerifyResult:
    """Check every event of the log against its hash and its link to the previous event.

    Args:
        path: Location of the log file.

    Returns:
        The result, with the first broken line if there is one.
    """
    prev = GENESIS
    count = 0
    if not Path(path).exists():
        return VerifyResult(True, 0, problem="No audit log yet.")
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return VerifyResult(False, count, line_no, "Line is not valid JSON.")
            stored = record.pop("hash", None)
            if record.get("prev_hash") != prev:
                return VerifyResult(False, count, line_no, "Link to the previous event is broken.")
            if _hash(record) != stored:
                return VerifyResult(False, count, line_no, "Content does not match its hash.")
            prev, count = stored, count + 1
    return VerifyResult(True, count)
