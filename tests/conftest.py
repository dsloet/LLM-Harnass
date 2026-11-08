"""Shared test setup: a real config, pointed at temporary folders."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.audit.log import LOG_NAME
from harness.config import Settings, load_settings
from harness.loop import SessionResult, run_session
from harness.model.scripted import ScriptedModel

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Load the real config, pointed at temporary folders, with tracing off.

    Args:
        tmp_path: Temporary folder for this test.
        monkeypatch: Pytest helper that sets the environment variables for this test.

    Returns:
        The settings, with a small workspace already filled in.
    """
    workspace = tmp_path / "workspace"
    (workspace / "secrets").mkdir(parents=True)
    (workspace / "notes.txt").write_text("Quarterly price review is due in December.\n")
    (workspace / "report_draft.md").write_text("# Draft\noriginal text\n")
    (workspace / "secrets" / "token.env").write_text("API_TOKEN=fake-token-123\n")
    monkeypatch.setenv("HARNESS_CONFIG_DIR", str(REPO / "config"))
    monkeypatch.setenv("HARNESS_DATA_DIR", str(REPO / "data"))
    monkeypatch.setenv("HARNESS_WORKSPACE", str(workspace))
    monkeypatch.setenv("HARNESS_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("HARNESS_OUTBOX_DIR", str(tmp_path / "outbox"))
    monkeypatch.setenv("HARNESS_APPROVAL", "deny")
    loaded = load_settings(REPO / "config" / "harness.yaml")
    return with_changes(loaded, telemetry={"enabled": False})


def with_changes(settings: Settings, **sections: dict) -> Settings:
    """Return a copy of the settings with some fields of some sections changed.

    Args:
        settings: The settings to copy.
        **sections: For each section name, a dictionary of the fields to change.

    Returns:
        The changed copy. The original is not modified.
    """
    update = {name: getattr(settings, name).model_copy(update=values) for name, values in sections.items()}
    return settings.model_copy(update=update)


def run_scenario(settings: Settings, name: str, role: str = "analyst") -> SessionResult:
    """Run one scenario file with the scripted model.

    Args:
        settings: The settings to run with.
        name: File name of the scenario in the ``scenarios`` folder.
        role: Role of the test user.

    Returns:
        The result of the session.
    """
    model = ScriptedModel(REPO / "scenarios" / name)
    return run_session(settings, model, f"scenario {name}", user="tester", role=role)


def audit_events(settings: Settings) -> list[dict]:
    """Read all events of the audit log.

    Args:
        settings: The settings that say where the log is.

    Returns:
        One dictionary per event.
    """
    path = settings.paths.audit_dir / LOG_NAME
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def events_named(settings: Settings, name: str) -> list[dict]:
    """Pick the data of all audit events with one name.

    Args:
        settings: The settings that say where the log is.
        name: The event name to look for.

    Returns:
        The ``data`` part of each matching event.
    """
    return [e["data"] for e in audit_events(settings) if e["event"] == name]
