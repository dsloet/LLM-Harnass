"""Load and validate the YAML configuration.

Why validate? A typo in a security setting (``fail_closd: true``) must stop
the harness at start-up, not silently fall back to an unsafe default. Pydantic
rejects unknown keys (``extra="forbid"``) and wrong types.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


class _Strict(BaseModel):
    """Base class for all settings: unknown keys are errors and values cannot change."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelSettings(_Strict):
    """Which model to talk to.

    Attributes:
        provider: ``ollama`` for the real model, ``scripted`` for a scenario replay.
        name: Model name as the server knows it.
        url: Base URL of the model server.
        temperature: Sampling temperature. 0 gives the most repeatable output.
        timeout_seconds: How long to wait for one model reply.
        scenario: Path of the scenario file, only used by the scripted provider.
    """

    provider: Literal["ollama", "scripted"]
    name: str
    url: str
    temperature: float = 0
    timeout_seconds: int = 180
    scenario: str | None = None


class PathSettings(_Strict):
    """Directories the harness reads and writes.

    Attributes:
        config_dir: Folder with the YAML configuration files.
        data_dir: Folder with the records and documents the tools can search.
        workspace: The only folder the file tools may touch.
        audit_dir: Where the audit log and stored model calls go.
        outbox_dir: Where outgoing messages are written instead of being sent.
    """

    config_dir: Path
    data_dir: Path
    workspace: Path
    audit_dir: Path
    outbox_dir: Path


class LimitSettings(_Strict):
    """Hard limits that stop a run that goes on too long.

    Attributes:
        max_steps: Maximum number of model calls in one session.
        max_seconds: Maximum wall-clock time of one session.
        max_output_chars: Longest tool output the model gets to see.
    """

    max_steps: int = Field(gt=0)
    max_seconds: int = Field(gt=0)
    max_output_chars: int = Field(gt=100)


class ApprovalSettings(_Strict):
    """How calls that need a person are handled.

    Attributes:
        mode: ``prompt`` asks at the terminal, ``deny`` refuses, ``approve`` allows (tests only).
    """

    mode: Literal["prompt", "deny", "approve"]


class EgressSettings(_Strict):
    """Rules for network traffic that leaves the harness.

    Attributes:
        allowed_domains: The only hosts the network tool may contact.
    """

    allowed_domains: list[str] = []


class RunCommandSettings(_Strict):
    """Settings for the ``run_command`` tool.

    Attributes:
        allowed_binaries: Programs the tool may start.
        timeout_seconds: How long one command may run.
    """

    allowed_binaries: list[str]
    timeout_seconds: int = 10


class ToolSettings(_Strict):
    """Which tools exist and how they are limited.

    Attributes:
        enabled: Names of the tools the model can use.
        run_command: Settings for the ``run_command`` tool.
    """

    enabled: list[str]
    run_command: RunCommandSettings


class ContextSettings(_Strict):
    """How the model's context is built and checked.

    Attributes:
        trust_labels: Wrap each item in a label that states how far it can be trusted.
        require_citations: Fail the final answer if it cites no sources.
    """

    trust_labels: bool = True
    require_citations: bool = True


class HookSettings(_Strict):
    """Settings for the checks around each tool call.

    Attributes:
        fail_closed: Treat a crashing hook as a block instead of ignoring it.
        enabled: Names of the hooks to run.
    """

    fail_closed: bool = True
    enabled: list[str] = []


class TelemetrySettings(_Strict):
    """Settings for OpenTelemetry tracing.

    Attributes:
        enabled: Turn tracing on or off.
        service_name: Name shown for this service in the trace viewer.
        otlp_endpoint: Base URL of the OTLP HTTP collector.
    """

    enabled: bool = True
    service_name: str = "llm-harness"
    otlp_endpoint: str = "http://localhost:4318"


class Settings(_Strict):
    """The complete validated configuration.

    Attributes:
        model: Model settings.
        paths: Directory settings.
        limits: Run limits.
        approval: Approval settings.
        egress: Network egress settings.
        tools: Tool settings.
        context: Context settings.
        hooks: Hook settings.
        telemetry: Tracing settings.
    """

    model: ModelSettings
    paths: PathSettings
    limits: LimitSettings
    approval: ApprovalSettings
    egress: EgressSettings
    tools: ToolSettings
    context: ContextSettings
    hooks: HookSettings
    telemetry: TelemetrySettings

    def fingerprint(self) -> str:
        """Return a short hash of the effective settings.

        It is written to every audit session, so you can see which settings were active.

        Returns:
            The first 16 hex characters of the SHA-256 hash.
        """
        raw = self.model_dump_json().encode()
        return hashlib.sha256(raw).hexdigest()[:16]


def expand_env(text: str) -> str:
    """Replace ${NAME} and ${NAME:-default} with environment values.

    Args:
        text: Text that may contain placeholders.

    Returns:
        The text with every placeholder replaced.

    Raises:
        ValueError: If a variable is not set and the placeholder has no default.
    """

    def _sub(match: re.Match[str]) -> str:
        """Return the replacement text for one placeholder match."""
        name, default = match.group(1), match.group(2)
        value = os.environ.get(name)
        if value is None:
            if default is None:
                raise ValueError(f"Environment variable {name} is not set and has no default")
            return default
        return value

    return _ENV_PATTERN.sub(_sub, text)


def load_yaml(path: Path) -> dict:
    """Read a YAML file after expanding environment variables.

    Args:
        path: Location of the YAML file.

    Returns:
        The parsed top-level mapping.

    Raises:
        ValueError: If the file does not contain a YAML mapping.
    """
    text = expand_env(Path(path).read_text(encoding="utf-8"))
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_settings(path: Path) -> Settings:
    """Read and validate the settings file.

    Args:
        path: Location of ``harness.yaml``.

    Returns:
        The validated settings. Pydantic raises an error for unknown keys or wrong types.
    """
    return Settings.model_validate(load_yaml(path))


def file_fingerprint(path: Path) -> str:
    """Hash a config file, so the audit log records exactly which policy ran.

    Args:
        path: Location of the file.

    Returns:
        The first 16 hex characters of the SHA-256 hash of the file.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
