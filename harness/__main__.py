"""Command line: python -m harness <command>.

Commands:

    run "task"                 run an agent session
    policy-check TOOL ARGS     dry-run the policy gate for one tool call
    verify-audit               check the audit log's hash chain
    show-call CALL_ID          show exactly what the model saw in one call
    revert SESSION_ID          undo the file writes of one session
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from harness.audit.log import LOG_NAME, verify_chain
from harness.config import Settings, load_settings, load_yaml
from harness.model import build_model
from harness.model.base import ToolCall
from harness.policy.gate import PolicyError, PolicyGate
from harness.tools.files import revert_session

DEFAULT_CONFIG = os.environ.get("HARNESS_CONFIG", "/app/config/harness.yaml")


def main(argv: list[str] | None = None) -> int:
    """Run the command line and return the process exit code.

    Args:
        argv: Command line arguments without the program name. None means
            use ``sys.argv``. Tests pass a list here.

    Returns:
        0 on success, 1 when a check fails, 2 on a configuration error.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = _parser().parse_args(argv)
    try:
        settings = load_settings(Path(args.config))
        return args.handler(args, settings)
    except (PolicyError, ValueError, FileNotFoundError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser with one sub-command per action.

    Returns:
        The parser. Each sub-command stores its handler function in ``args.handler``.
    """
    parser = argparse.ArgumentParser(prog="harness", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to harness.yaml")
    sub = parser.add_subparsers(required=True)

    run = sub.add_parser("run", help="run an agent session")
    run.add_argument("task")
    run.add_argument("--user", default="student")
    run.add_argument("--role", default="analyst", help="used by the access filter on records")
    run.add_argument("--scenario", help="replay a scripted model instead of the real one")
    run.add_argument("--approval", choices=["prompt", "deny", "approve"], help="override approval.mode")
    run.set_defaults(handler=_cmd_run)

    check = sub.add_parser("policy-check", help="dry-run the policy gate")
    check.add_argument("tool")
    check.add_argument("arguments", help='JSON, for example \'{"argv": ["rm", "-rf", "x"]}\'')
    check.set_defaults(handler=_cmd_policy_check)

    verify = sub.add_parser("verify-audit", help="check the audit hash chain")
    verify.set_defaults(handler=_cmd_verify)

    show = sub.add_parser("show-call", help="show the context manifest of one model call")
    show.add_argument("call_id")
    show.set_defaults(handler=_cmd_show_call)

    revert = sub.add_parser("revert", help="undo the file writes of one session")
    revert.add_argument("session_id")
    revert.set_defaults(handler=_cmd_revert)
    return parser


def _cmd_run(args: argparse.Namespace, settings: Settings) -> int:
    """Run one agent session.

    Args:
        args: Parsed command line arguments.
        settings: The validated settings.

    Returns:
        The exit code, always 0.
    """
    from harness.loop import run_session  # imported here: tracing setup is only needed for runs

    model_update = {"provider": "scripted", "scenario": args.scenario} if args.scenario else {}
    update: dict = {"model": settings.model.model_copy(update=model_update)}
    if args.approval:
        update["approval"] = settings.approval.model_copy(update={"mode": args.approval})
    settings = settings.model_copy(update=update)
    run_session(settings, build_model(settings.model), args.task, args.user, args.role)
    return 0


def _cmd_policy_check(args: argparse.Namespace, settings: Settings) -> int:
    """Show the policy verdict for one tool call without running it.

    Args:
        args: Parsed command line arguments with the tool name and JSON arguments.
        settings: The validated settings.

    Returns:
        The exit code, always 0.
    """
    gate = PolicyGate(load_yaml(settings.paths.config_dir / "policy.yaml"))
    verdict = gate.evaluate(ToolCall(args.tool, json.loads(args.arguments)))
    print(f"{verdict.decision.value.upper()}  rule={verdict.rule_id}  {verdict.reason}")
    return 0


def _cmd_verify(args: argparse.Namespace, settings: Settings) -> int:
    """Check the hash chain of the audit log.

    Args:
        args: Parsed command line arguments (not used).
        settings: The validated settings.

    Returns:
        0 if the chain is intact, 1 if it is broken.
    """
    result = verify_chain(settings.paths.audit_dir / LOG_NAME)
    if result.ok:
        print(f"OK: {result.events} events, hash chain intact. {result.problem}".strip())
        return 0
    print(f"BROKEN at line {result.first_bad_line}: {result.problem} "
          f"({result.events} events before it are intact)")
    return 1


def _cmd_show_call(args: argparse.Namespace, settings: Settings) -> int:
    """Print the context manifest that was stored for one model call.

    Args:
        args: Parsed command line arguments with the call ID.
        settings: The validated settings.

    Returns:
        0 if the call was found, 1 if it was not.
    """
    path = settings.paths.audit_dir / "calls" / f"{args.call_id}.json"
    if not path.exists():
        print(f"No stored call {args.call_id}. Call IDs are in the model_call events of the audit log.")
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(f"Model call {args.call_id} ({payload['model']})\n")
    print(f"{'source':32} {'trust':10} {'version':26} sha256")
    for entry in payload["manifest"]:
        print(f"{entry['source_id']:32} {entry['trust']:10} {entry['version'][:26]:26} "
              f"{entry['sha256'][:12]}")
    print(f"\n{len(payload['messages'])} messages; full prompt in {path}")
    return 0


def _cmd_revert(args: argparse.Namespace, settings: Settings) -> int:
    """Undo the file writes of one session.

    Args:
        args: Parsed command line arguments with the session ID.
        settings: The validated settings.

    Returns:
        The exit code, always 0.
    """
    done = revert_session(settings.paths.audit_dir, settings.paths.workspace, args.session_id)
    print("\n".join(done) if done else "No writes recorded for that session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
