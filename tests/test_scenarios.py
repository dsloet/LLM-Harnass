"""End-to-end runs of the lesson scenarios with the scripted model."""
from harness.audit.log import LOG_NAME, verify_chain

from conftest import events_named, run_scenario, with_changes


def test_hello_scenario_answers_with_a_valid_citation(settings):
    result = run_scenario(settings, "01_hello.yaml")
    assert result.stop_reason == "final_answer"
    assert result.citations.ok
    assert verify_chain(settings.paths.audit_dir / LOG_NAME).ok


def test_injection_is_contained(settings):
    result = run_scenario(settings, "04_injection.yaml", role="analyst")
    decisions = {d["n"]: d["decision"] for d in events_named(settings, "policy_decision")}
    assert decisions[3] == "ask" and decisions[4] == "ask"         # fetch_url, send_email
    assert all(not a["approved"] for a in events_named(settings, "approval"))
    assert not settings.paths.outbox_dir.exists() or not any(settings.paths.outbox_dir.iterdir())
    assert events_named(settings, "access_filter")[0]["withheld"] == ["rec-002"]
    flags = [r["flags"] for r in events_named(settings, "tool_result") if r["flags"]]
    assert any("possible_injection" in f for f in flags)
    assert result.citations.ok


def test_even_an_approved_fetch_cannot_leave(settings):
    approving = with_changes(settings, approval={"mode": "approve"})
    run_scenario(approving, "04_injection.yaml", role="manager")
    errors = [e["error"] for e in events_named(approving, "tool_error")]
    assert any("Egress blocked" in e for e in errors)


def test_destructive_scenario_changes_nothing(settings):
    before = (settings.paths.workspace / "report_draft.md").read_text()
    run_scenario(settings, "03_destructive.yaml")
    assert (settings.paths.workspace / "report_draft.md").read_text() == before
    assert (settings.paths.workspace / "notes.txt").exists()


def test_policy_gap_is_caught_by_the_secret_redactor(settings):
    run_scenario(settings, "02_policy.yaml")
    flags = [r["flags"] for r in events_named(settings, "tool_result")]
    assert any("secrets_redacted" in f for f in flags)


def test_invented_citation_is_reported(settings):
    result = run_scenario(settings, "06_provenance.yaml")
    assert result.citations.unknown == ("records:rec-999",)
    calls = events_named(settings, "model_call")
    assert any(e["source_id"] == "records:rec-001" for e in calls[-1]["manifest"])


def test_runaway_model_is_stopped_by_the_step_limit(settings):
    result = run_scenario(settings, "07_runaway.yaml")
    assert result.stop_reason == "step_limit"
    assert len(events_named(settings, "model_call")) == settings.limits.max_steps


def test_crashing_hook_blocks_when_fail_closed(settings):
    broken = with_changes(settings, hooks={"enabled": ["always_crashes"], "fail_closed": True})
    run_scenario(broken, "01_hello.yaml")
    assert len(events_named(broken, "hook_blocked")) == 2


def test_crashing_hook_is_ignored_when_fail_open(settings):
    broken = with_changes(settings, hooks={"enabled": ["always_crashes"], "fail_closed": False})
    run_scenario(broken, "01_hello.yaml")
    assert events_named(broken, "hook_blocked") == []
    assert len(events_named(broken, "hook_error")) == 2
