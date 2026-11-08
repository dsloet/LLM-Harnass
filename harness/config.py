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
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelSettings(_Strict):
    provider: Literal["ollama", "scripted"]
    name: str
    url: str
    temperature: float = 0
    timeout_seconds: int = 180
    scenario: str | None = None


class PathSettings(_Strict):
    config_dir: Path
    data_dir: Path
    workspace: Path
    audit_dir: Path
    outbox_dir: Path


class LimitSettings(_Strict):
    max_steps: int = Field(gt=0)
    max_seconds: int = Field(gt=0)
    max_output_chars: int = Field(gt=100)


class ApprovalSettings(_Strict):
    mode: Literal["prompt", "deny", "approve"]


class EgressSettings(_Strict):
    allowed_domains: list[str] = []


class RunCommandSettings(_Strict):
    allowed_binaries: list[str]
    timeout_seconds: int = 10


class ToolSettings(_Strict):
    enabled: list[str]
    run_command: RunCommandSettings


class ContextSettings(_Strict):
    trust_labels: bool = True
    require_citations: bool = True


class HookSettings(_Strict):
    fail_closed: bool = True
    enabled: list[str] = []


class TelemetrySettings(_Strict):
    enabled: bool = True
    service_name: str = "llm-harness"
    otlp_endpoint: str = "http://localhost:4318"


class Settings(_Strict):
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
        """Short hash of the effective settings, written to every audit session."""
        raw = self.model_dump_json().encode()
        return hashlib.sha256(raw).hexdigest()[:16]


def expand_env(text: str) -> str:
    """Replace ${NAME} and ${NAME:-default} with environment values."""

    def _sub(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        value = os.environ.get(name)
        if value is None:
            if default is None:
                raise ValueError(f"Environment variable {name} is not set and has no default")
            return default
        return value

    return _ENV_PATTERN.sub(_sub, text)


def load_yaml(path: Path) -> dict:
    """Read a YAML file after expanding environment variables."""
    text = expand_env(Path(path).read_text(encoding="utf-8"))
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_settings(path: Path) -> Settings:
    return Settings.model_validate(load_yaml(path))


def file_fingerprint(path: Path) -> str:
    """Hash of a config file, so the audit log records exactly which policy ran."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
