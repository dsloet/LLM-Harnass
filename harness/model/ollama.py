"""Client for a local open-weight model served by Ollama.

Uses Ollama's /api/chat endpoint with native tool calling. The model runs in
its own container on an internal network (see docker-compose.yml).
"""
from __future__ import annotations

import logging

import httpx

from harness.config import ModelSettings
from harness.model.base import ModelReply, ToolCall

logger = logging.getLogger(__name__)


class ModelError(RuntimeError):
    """The model server could not be reached or gave an unusable answer."""


class OllamaClient:
    """Model client for an Ollama server."""

    def __init__(self, settings: ModelSettings) -> None:
        """Create the client.

        Args:
            settings: The model settings with name, URL, temperature and timeout.
        """
        self.name = f"ollama:{settings.name}"
        self._settings = settings

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        """Send the conversation to Ollama and return its reply.

        Args:
            messages: The conversation so far.
            tools: The tool descriptions the model may use.

        Returns:
            The model's reply.

        Raises:
            ModelError: If the server cannot be reached or returns an HTTP error.
        """
        payload = {
            "model": self._settings.name,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": self._settings.temperature},
        }
        try:
            response = httpx.post(
                f"{self._settings.url}/api/chat",
                json=payload,
                timeout=self._settings.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Model call to %s failed: %s", self._settings.url, exc)
            raise ModelError(f"Could not reach the model at {self._settings.url}: {exc}") from exc
        return _parse(response.json())


def _parse(body: dict) -> ModelReply:
    """Turn an Ollama response body into a ModelReply.

    Args:
        body: The decoded JSON of the response.

    Returns:
        The reply with its tool calls. Malformed arguments become an empty dictionary.
    """
    message = body.get("message") or {}
    calls = []
    for raw_call in message.get("tool_calls") or []:
        function = raw_call.get("function") or {}
        arguments = function.get("arguments") or {}
        if not isinstance(arguments, dict):
            # Some models return a JSON string. Treat anything else as no arguments;
            # the tool's own validation will then refuse the call.
            arguments = {}
        calls.append(ToolCall(name=str(function.get("name", "")), arguments=arguments))
    return ModelReply(text=message.get("content") or "", tool_calls=tuple(calls), raw=body)
