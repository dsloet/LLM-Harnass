"""Tools that reach outside: fetch_url and send_email.

These are the classic exfiltration paths (report risk 7). Three layers stop
an injected "send the customer list to attacker.example":
  1. the policy gate asks a person (config/policy.yaml),
  2. fetch_url refuses every host not in egress.allowed_domains,
  3. the harness container sits on an internal Docker network with no route
     to the internet at all (docker-compose.yml).
send_email only writes to the outbox folder; nothing is actually sent.
"""
from __future__ import annotations

import json
import uuid
from urllib.parse import urlparse

import httpx

from harness.context.ledger import now_iso
from harness.tools.base import Tool, ToolContext, ToolError, ToolOutput, require_str


def _fetch_url(arguments: dict, ctx: ToolContext) -> ToolOutput:
    """Fetch a page, but only from hosts in the egress allow-list.

    Args:
        arguments: The ``url`` to fetch.
        ctx: The tool context.

    Returns:
        The HTTP status and the body.

    Raises:
        ToolError: If the scheme is not http or https, the host is not allowed,
            or the request fails.
    """
    url = require_str(arguments, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ToolError("Only http and https URLs are allowed.")
    host = parsed.hostname or ""
    if host not in ctx.settings.egress.allowed_domains:
        raise ToolError(f"Egress blocked: '{host}' is not in egress.allowed_domains.")
    try:
        response = httpx.get(url, timeout=10, follow_redirects=False)
    except httpx.HTTPError as exc:
        raise ToolError(f"Request failed: {exc}") from exc
    return ToolOutput(f"HTTP {response.status_code}\n{response.text}")


def _send_email(arguments: dict, ctx: ToolContext) -> ToolOutput:
    """Queue an email in the outbox folder. Nothing is sent.

    Args:
        arguments: The ``to``, ``subject`` and ``body`` of the message.
        ctx: The tool context.

    Returns:
        A confirmation with the message ID.
    """
    message = {
        "id": uuid.uuid4().hex[:8],
        "queued_at": now_iso(),
        "session": ctx.session_id,
        "on_behalf_of": ctx.user,
        "to": require_str(arguments, "to"),
        "subject": require_str(arguments, "subject"),
        "body": require_str(arguments, "body"),
    }
    outbox = ctx.settings.paths.outbox_dir
    outbox.mkdir(parents=True, exist_ok=True)
    (outbox / f"{message['id']}.json").write_text(json.dumps(message, indent=2))
    return ToolOutput(f"Email queued in the outbox as {message['id']}.")


TOOLS = [
    Tool("fetch_url", "Fetch a web page by URL.",
         {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
         _fetch_url),
    Tool("send_email", "Send an email.",
         {"type": "object",
          "properties": {"to": {"type": "string"}, "subject": {"type": "string"},
                         "body": {"type": "string"}},
          "required": ["to", "subject", "body"]},
         _send_email),
]
