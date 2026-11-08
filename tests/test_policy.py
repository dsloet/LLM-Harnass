import pytest

from harness.config import load_yaml
from harness.model.base import ToolCall
from harness.policy.gate import Decision, PolicyError, PolicyGate

from conftest import REPO


@pytest.fixture
def gate() -> PolicyGate:
    return PolicyGate(load_yaml(REPO / "config" / "policy.yaml"))


def test_unknown_program_falls_to_default_deny(gate):
    verdict = gate.evaluate(ToolCall("run_command", {"argv": ["tar", "-czf", "x.tgz", "."]}))
    assert verdict.decision is Decision.DENY
    assert verdict.rule_id == "default"


def test_delete_is_denied_even_with_a_full_path(gate):
    verdict = gate.evaluate(ToolCall("run_command", {"argv": ["/bin/rm", "-rf", "."]}))
    assert verdict.decision is Decision.DENY
    assert verdict.rule_id == "no-delete-commands"


def test_shell_chaining_is_just_arguments_to_ls(gate):
    # Allowed, because it IS only ls: the tool never hands this to a shell.
    verdict = gate.evaluate(ToolCall("run_command", {"argv": ["ls", "&&", "rm", "-rf", "x"]}))
    assert verdict.decision is Decision.ALLOW


def test_deny_beats_allow_for_secret_files(gate):
    verdict = gate.evaluate(ToolCall("read_file", {"path": "secrets/token.env"}))
    assert verdict.decision is Decision.DENY
    assert verdict.rule_id == "no-secret-files"


def test_outbound_actions_need_a_person(gate):
    assert gate.evaluate(ToolCall("send_email", {"to": "a@b.example"})).decision is Decision.ASK
    assert gate.evaluate(ToolCall("fetch_url", {"url": "https://x.example"})).decision is Decision.ASK


def test_default_allow_lets_unknown_calls_through():
    # What lesson 2 warns about: flip the default and anything unforeseen runs.
    gate = PolicyGate({"default": "allow", "rules": []})
    assert gate.evaluate(ToolCall("run_command", {"argv": ["tar"]})).decision is Decision.ALLOW


@pytest.mark.parametrize("policy", [
    {"default": "maybe", "rules": []},
    {"default": "deny", "rules": [{"id": "x", "action": "allow", "tool": "read_file", "when": {"typo": 1}}]},
    {"default": "deny", "rules": [{"id": "x", "action": "allow"}]},
])
def test_invalid_policy_stops_the_harness(policy):
    with pytest.raises(PolicyError):
        PolicyGate(policy)
