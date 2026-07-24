from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from evomind.config.settings import Settings


class MeterManager:
    """Manages the OpenTelemetry MeterProvider lifecycle."""

    def __init__(self, settings: Settings, exporter: MetricExporter | None = None) -> None:
        self._settings = settings
        self._exporter = exporter
        self._provider: MeterProvider | None = None

    def initialize(self) -> None:
        resource = Resource.create(
            {
                "service.name": self._settings.otel_service_name,
                "service.version": self._settings.app_version,
            }
        )
        self._provider = MeterProvider(resource=resource)
        if self._exporter is not None:
            reader = PeriodicExportingMetricReader(self._exporter)
            self._provider.add_metric_reader(reader)
        metrics.set_meter_provider(self._provider)

    @property
    def meter(self) -> metrics.Meter:
        if self._provider is None:
            raise RuntimeError(
                "MeterManager not initialized. Call initialize() first."
            )
        return metrics.get_meter(self._settings.otel_service_name)

    def shutdown(self) -> None:
        if self._provider is not None:
            self._provider.shutdown()
