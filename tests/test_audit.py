"""Tests for the tamper-evident audit log."""
import json

from harness.audit.log import LOG_NAME, AuditLog, verify_chain


def test_chain_verifies_and_continues_across_sessions(tmp_path):
    """The chain stays valid when a second session appends to the same log."""
    first = AuditLog(tmp_path)
    first.append("a", {"x": 1})
    second = AuditLog(tmp_path)          # a new session appends to the same chain
    second.append("b", {"x": 2})
    result = verify_chain(tmp_path / LOG_NAME)
    assert result.ok and result.events == 2


def test_editing_one_event_is_detected(tmp_path):
    """Changing one event is found, and the bad line is reported."""
    log = AuditLog(tmp_path)
    for i in range(3):
        log.append("tool_proposed", {"n": i})
    path = tmp_path / LOG_NAME
    lines = path.read_text().splitlines()
    record = json.loads(lines[1])
    record["data"]["n"] = 99              # someone "corrects" the log
    lines[1] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n")
    result = verify_chain(path)
    assert not result.ok
    assert result.first_bad_line == 2


def test_deleting_an_event_is_detected(tmp_path):
    """Removing one event breaks the chain."""
    log = AuditLog(tmp_path)
    for i in range(3):
        log.append("e", {"n": i})
    path = tmp_path / LOG_NAME
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert not verify_chain(path).ok
