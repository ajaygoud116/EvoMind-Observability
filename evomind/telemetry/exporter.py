from __future__ import annotations

from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics.export import MetricExporter
from opentelemetry.sdk.trace.export import SpanExporter

from evomind.config.settings import Settings
from evomind.exceptions.errors import TelemetryError


class ExporterConfig:
    """Configures and creates OTLP exporters."""

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

    @staticmethod
    def create_metric_exporter(settings: Settings) -> MetricExporter | None:
        if not settings.is_telemetry_enabled:
            return None

        try:
            return OTLPMetricExporter(
                endpoint=settings.otel_exporter_endpoint,
                insecure=settings.otel_exporter_insecure,
            )
        except Exception as exc:
            raise TelemetryError(
                f"Failed to create OTLP metric exporter: {exc}"
            ) from exc
