"""run_command: run a program with an argument LIST, never through a shell.

Why an argument list? With a shell, the text ``ls && rm -rf data`` is two
commands. Without a shell, it is the program ``ls`` called with the
arguments ``&&``, ``rm``, ``-rf`` and ``data``: ls complains that those
files do not exist, and nothing is deleted. There is no string to inject into.

Extra checks inside the tool (on top of the policy gate):
  * the program must be in tools.run_command.allowed_binaries
  * arguments that look like paths must stay inside the workspace
  * a time limit, an empty environment, and the workspace as working folder

What this does NOT stop: an allowed interpreter such as python can do
anything the agent user can do. That is why the policy asks a person first,
and why the container itself is the real sandbox.
"""
from __future__ import annotations

import subprocess
from pathlib import PurePosixPath

from harness.tools.base import Tool, ToolContext, ToolError, ToolOutput, confine

_SAFE_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"}


def _run_command(arguments: dict, ctx: ToolContext) -> ToolOutput:
    """Run an allowed program with an argument list, without a shell.

    Args:
        arguments: The ``argv`` list. The first item is the program.
        ctx: The tool context.

    Returns:
        The exit code and the output of the program.

    Raises:
        ToolError: If ``argv`` is invalid, the program is not allowed, a path argument
            leaves the workspace, the command times out or the program is missing.
    """
    argv = arguments.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ToolError("Argument 'argv' must be a non-empty list of strings.")
    settings = ctx.settings.tools.run_command
    program = PurePosixPath(argv[0]).name
    if program not in settings.allowed_binaries:
        raise ToolError(f"Program '{program}' is not on the allowed list.")
    workspace = ctx.settings.paths.workspace
    for arg in argv[1:]:
        if arg.startswith("/") or ".." in arg:
            confine(workspace, arg)
    try:
        result = subprocess.run(
            [program, *argv[1:]],
            cwd=workspace,
            env=_SAFE_ENV,
            capture_output=True,
            text=True,
            timeout=settings.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"Command stopped after {settings.timeout_seconds} seconds.") from exc
    except FileNotFoundError as exc:
        raise ToolError(f"Program '{program}' is not installed.") from exc
    output = f"exit code {result.returncode}\n{result.stdout}{result.stderr}"
    return ToolOutput(output)


TOOLS = [
    Tool(
        "run_command",
        "Run a program in the workspace. Give the program and its arguments as a list, "
        'for example ["grep", "-n", "price", "notes.txt"]. No shell features.',
        {
            "type": "object",
            "properties": {"argv": {"type": "array", "items": {"type": "string"}}},
            "required": ["argv"],
        },
        _run_command,
    ),
]
