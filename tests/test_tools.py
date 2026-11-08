import pytest

from harness.context.sources import SourceCatalog
from harness.tools import ALL_TOOLS
from harness.tools.base import ToolContext, ToolError
from harness.tools.files import revert_session


@pytest.fixture
def ctx(settings) -> ToolContext:
    return ToolContext(settings=settings, catalog=SourceCatalog(settings),
                       user="tester", role="analyst", session_id="s1")


def run(name, args, ctx):
    return ALL_TOOLS[name].run(args, ctx)


@pytest.mark.parametrize("path", ["../outside.txt", "/etc/passwd", "secrets/../../x"])
def test_file_tools_stay_in_the_workspace(ctx, path):
    with pytest.raises(ToolError, match="outside the workspace"):
        run("read_file", {"path": path}, ctx)


def test_no_shell_means_chaining_does_nothing(ctx, settings):
    output = run("run_command", {"argv": ["ls", "&&", "rm", "-rf", "notes.txt"]}, ctx)
    assert "exit code" in output.text
    assert (settings.paths.workspace / "notes.txt").exists()


def test_program_must_be_allowed_inside_the_tool_too(ctx):
    # Defence in depth: even if the policy were wrong, the tool refuses.
    with pytest.raises(ToolError, match="not on the allowed list"):
        run("run_command", {"argv": ["rm", "notes.txt"]}, ctx)


def test_command_paths_stay_in_the_workspace(ctx):
    with pytest.raises(ToolError, match="outside the workspace"):
        run("run_command", {"argv": ["cat", "/etc/passwd"]}, ctx)


def test_egress_allowlist_blocks_unknown_hosts(ctx):
    with pytest.raises(ToolError, match="Egress blocked"):
        run("fetch_url", {"url": "https://collector.attacker.example/x"}, ctx)


def test_write_keeps_a_snapshot_and_revert_restores(ctx, settings):
    target = settings.paths.workspace / "report_draft.md"
    original = target.read_text()
    run("write_file", {"path": "report_draft.md", "content": "(empty)"}, ctx)
    run("write_file", {"path": "new.txt", "content": "hello"}, ctx)
    assert target.read_text() == "(empty)"
    done = revert_session(settings.paths.audit_dir, settings.paths.workspace, "s1")
    assert target.read_text() == original
    assert not (settings.paths.workspace / "new.txt").exists()
    assert len(done) == 2
