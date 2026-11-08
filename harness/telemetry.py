"""OpenTelemetry tracing.

One trace per session. Inside it: a span per model call, per policy check and
per tool call, with the decision and the rule as attributes. Open Jaeger at
http://localhost:16686 to see the timeline (lesson 5).

Traces answer "what happened, in what order, how long did it take".
The audit log answers "can we prove it". You want both.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from harness.config import TelemetrySettings

logger = logging.getLogger(__name__)
_provider: TracerProvider | None = None


def init_tracing(settings: TelemetrySettings) -> trace.Tracer:
    """Set up export to the OTLP endpoint, or return a tracer that does nothing."""
    global _provider
    if not settings.enabled:
        return trace.NoOpTracer()
    if _provider is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        _provider = TracerProvider(resource=Resource.create({"service.name": settings.service_name}))
        exporter = OTLPSpanExporter(endpoint=f"{settings.otlp_endpoint.rstrip('/')}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(exporter))
    return _provider.get_tracer("llm-harness")


def shutdown_tracing() -> None:
    """Flush spans before the process exits. Export errors are logged, not fatal."""
    if _provider is not None:
        try:
            _provider.shutdown()
        except Exception as exc:  # noqa: BLE001 - tracing must never break a run
            logger.warning("Could not flush traces: %s", exc)


@contextmanager
def span(tracer: trace.Tracer, name: str, **attributes):
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value if isinstance(value, (str, int, float, bool)) else str(value))
        yield current
