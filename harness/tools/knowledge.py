"""Tools that bring company data into the context: search_records, read_inbox.

They return ContextItems with source IDs, so the data the model sees keeps
its provenance (report section 6).
"""
from __future__ import annotations

from harness.tools.base import Tool, ToolContext, ToolOutput, require_str


def _search_records(arguments: dict, ctx: ToolContext) -> ToolOutput:
    query = require_str(arguments, "query")
    result = ctx.catalog.search_records(query, ctx.role)
    if result.withheld:
        # Logged for the auditor; the model is only told that something was withheld.
        ctx.note("access_filter", {"query": query, "role": ctx.role, "withheld": list(result.withheld)})
    note = f" ({len(result.withheld)} matching record(s) withheld: no access)" if result.withheld else ""
    summary = f"{len(result.items)} record(s) found{note}."
    return ToolOutput(summary, result.items)


def _read_inbox(arguments: dict, ctx: ToolContext) -> ToolOutput:
    items = ctx.catalog.inbox()
    return ToolOutput(f"{len(items)} message(s) in the inbox.", items)


TOOLS = [
    Tool("search_records", "Search internal records. Returns only records you may see.",
         {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
         _search_records),
    Tool("read_inbox", "Read the messages in the shared inbox.",
         {"type": "object", "properties": {}}, _read_inbox),
]
