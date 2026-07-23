from __future__ import annotations

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import SpanExporter

from evomind.config.settings import Settings
from evomind.exceptions.errors import TelemetryError


class ExporterConfig:
    """Configures and creates the OTLP span exporter."""

    @staticmethod
    def create_span_exporter(settings: Settings) -> SpanExporter | None:
        if not settings.is_telemetry_enabled:
            return None

        try:
            return OTLPSpanExporter(
                endpoint=settings.otel_exporter_endpoint,
                insecure=settings.otel_exporter_insecure,
            )
        except Exception as exc:
            raise TelemetryError(
                f"Failed to create OTLP exporter: {exc}"
            ) from exc
