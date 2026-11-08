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
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _hash(record_without_hash: dict) -> str:
    return hashlib.sha256(_canonical(record_without_hash)).hexdigest()


class AuditLog:
    def __init__(self, audit_dir: Path, session_id: str | None = None) -> None:
        self.dir = Path(audit_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "calls").mkdir(exist_ok=True)
        self.path = self.dir / LOG_NAME
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self._prev_hash, self._seq = self._tail()

    def append(self, event: str, data: dict) -> dict:
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
        """Store the full prompt of one model call; return its hash for the log."""
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        (self.dir / "calls" / f"{call_id}.json").write_text(body, encoding="utf-8")
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _tail(self) -> tuple[str, int]:
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
    ok: bool
    events: int
    first_bad_line: int | None = None
    problem: str = ""


def verify_chain(path: Path) -> VerifyResult:
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
