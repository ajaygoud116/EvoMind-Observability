from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.resources import Resource

from evomind.config.settings import Settings


class TracerManager:
    """Manages the OpenTelemetry TracerProvider lifecycle."""

    def __init__(self, settings: Settings, exporter: SpanExporter | None = None) -> None:
        self._settings = settings
        self._exporter = exporter
        self._provider: TracerProvider | None = None

    def initialize(self) -> None:
        resource = Resource.create(
            {
                "service.name": self._settings.otel_service_name,
                "service.version": self._settings.app_version,
                "schema.version": self._settings.schema_version,
                "rule.version": self._settings.rule_version,
                "telemetry.version": self._settings.telemetry_version,
                "deployment.environment": "development",
            }
        )

        self._provider = TracerProvider(resource=resource)

        if self._exporter is not None:
            span_processor = BatchSpanProcessor(self._exporter)
            self._provider.add_span_processor(span_processor)

        trace.set_tracer_provider(self._provider)

    @property
    def tracer(self) -> trace.Tracer:
        if self._provider is None:
            raise RuntimeError(
                "TracerManager not initialized. Call initialize() first."
            )
        return trace.get_tracer(self._settings.otel_service_name)

    def shutdown(self) -> None:
        if self._provider is not None:
            self._provider.shutdown()

    @property
    def provider(self) -> TracerProvider | None:
        return self._provider
