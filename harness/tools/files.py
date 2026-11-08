"""File tools, confined to the workspace.

write_file keeps a snapshot of the old content OUTSIDE the workspace (in the
audit folder), so ``python -m harness revert <session>`` can undo a session's
writes. Report risk 2: destructive actions.
"""
from __future__ import annotations

import json
from pathlib import Path

from harness.tools.base import Tool, ToolContext, ToolError, ToolOutput, confine, require_str

MAX_LIST = 200


def _list_files(arguments: dict, ctx: ToolContext) -> ToolOutput:
    root = ctx.settings.paths.workspace
    folder = confine(root, str(arguments.get("path") or "."))
    if not folder.is_dir():
        raise ToolError(f"'{arguments.get('path')}' is not a folder in the workspace.")
    entries = sorted(str(p.relative_to(root.resolve())) for p in folder.rglob("*") if p.is_file())
    shown = entries[:MAX_LIST]
    suffix = f"\n... {len(entries) - MAX_LIST} more" if len(entries) > MAX_LIST else ""
    return ToolOutput("\n".join(shown) + suffix if shown else "(empty)")


def _read_file(arguments: dict, ctx: ToolContext) -> ToolOutput:
    path = confine(ctx.settings.paths.workspace, require_str(arguments, "path"))
    if not path.is_file():
        raise ToolError(f"No file '{arguments['path']}' in the workspace.")
    return ToolOutput(path.read_text(encoding="utf-8", errors="replace"))


def _write_file(arguments: dict, ctx: ToolContext) -> ToolOutput:
    relative = require_str(arguments, "path")
    content = arguments.get("content")
    if not isinstance(content, str):
        raise ToolError("Argument 'content' must be a string.")
    path = confine(ctx.settings.paths.workspace, relative)
    snapshot = _snapshot(path, relative, ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    ctx.note("snapshot_saved", {"path": relative, "snapshot": snapshot})
    return ToolOutput(f"Wrote {len(content)} characters to {relative}. A snapshot was kept.")


def _snapshot(path: Path, relative: str, ctx: ToolContext) -> str:
    folder = ctx.settings.paths.audit_dir / "snapshots" / ctx.session_id
    folder.mkdir(parents=True, exist_ok=True)
    index_path = folder / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else []
    name = f"{len(index) + 1:03d}.snap"
    existed = path.exists()
    if existed:
        (folder / name).write_bytes(path.read_bytes())
    index.append({"path": relative, "snapshot": name if existed else None})
    index_path.write_text(json.dumps(index, indent=2))
    return name if existed else "(new file)"


def revert_session(audit_dir: Path, workspace: Path, session_id: str) -> list[str]:
    """Undo every write of one session, newest first. Returns what was done."""
    folder = audit_dir / "snapshots" / session_id
    index_path = folder / "index.json"
    if not index_path.exists():
        return []
    done = []
    for entry in reversed(json.loads(index_path.read_text())):
        target = confine(workspace, entry["path"])
        if entry["snapshot"] is None:
            target.unlink(missing_ok=True)
            done.append(f"removed {entry['path']} (it was created in this session)")
        else:
            target.write_bytes((folder / entry["snapshot"]).read_bytes())
            done.append(f"restored {entry['path']}")
    return done


_PATH = {"type": "string", "description": "Path relative to the workspace."}

TOOLS = [
    Tool("list_files", "List files in a workspace folder.",
         {"type": "object", "properties": {"path": _PATH}}, _list_files),
    Tool("read_file", "Read a text file from the workspace.",
         {"type": "object", "properties": {"path": _PATH}, "required": ["path"]}, _read_file),
    Tool("write_file", "Create or overwrite a text file in the workspace.",
         {"type": "object",
          "properties": {"path": _PATH, "content": {"type": "string"}},
          "required": ["path", "content"]}, _write_file),
]
