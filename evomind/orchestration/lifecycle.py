from __future__ import annotations

import logging

from evomind.config.settings import Settings
from evomind.exceptions.errors import DatabaseError, TelemetryError
from evomind.orchestration.service_registry import ServiceRegistry
from evomind.persistence.database import Database
from evomind.telemetry.tracer import TracerManager
from evomind.telemetry.meter import MeterManager
from evomind.telemetry.helpers import SpanHelper

logger = logging.getLogger("evomind.lifecycle")


class LifecycleManager:
    """Manages application startup and shutdown sequence.

    Order:
    1. Load configuration
    2. Initialize telemetry (tracer + meter)
    3. Initialize database (schema + seed)
    4. Register core services
    5. Emit startup telemetry
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry = ServiceRegistry()
        self._tracer_manager: TracerManager | None = None
        self._meter_manager: MeterManager | None = None
        self._database: Database | None = None

    def startup(self) -> ServiceRegistry:
        logger.info(
            "Starting EvoMind Observability v%s",
            self._settings.app_version,
        )

        self._init_telemetry()
        self._init_database()
        self._register_core_services()
        self._emit_startup_trace()

        logger.info("Startup complete")
        return self._registry

    def shutdown(self) -> None:
        logger.info("Shutting down EvoMind Observability")

        if self._tracer_manager is not None:
            self._tracer_manager.shutdown()
        if self._meter_manager is not None:
            self._meter_manager.shutdown()
        if self._database is not None:
            self._database.close()

        logger.info("Shutdown complete")

    def _init_telemetry(self) -> None:
        from opentelemetry.sdk.trace.export import SpanExporter as _SpanExporter
        from evomind.telemetry.exporter import ExporterConfig

        if self._tracer_manager is None:
            self._tracer_manager = TracerManager(self._settings)
        if self._meter_manager is None:
            self._meter_manager = MeterManager(self._settings)

        exporter: _SpanExporter | None = None
        if self._settings.is_telemetry_enabled:
            exporter = ExporterConfig.create_span_exporter(self._settings)

        self._tracer_manager.initialize()
        if exporter is not None:
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            self._tracer_manager.provider.add_span_processor(
                BatchSpanProcessor(exporter)
            )
        self._meter_manager.initialize()

        self._registry.register("tracer_manager", self._tracer_manager)
        self._registry.register("meter_manager", self._meter_manager)

        logger.debug(
            "Telemetry initialized (endpoint=%s)",
            self._settings.otel_exporter_endpoint,
        )

    def _init_database(self) -> None:
        self._database = Database(self._settings)
        try:
            self._database.initialize()
        except DatabaseError as exc:
            logger.error("Database initialization failed: %s", exc)
            raise

        self._registry.register("database", self._database)

        rule_id = self._get_seeded_rule_id()
        if rule_id:
            self._registry.register("seeded_rule_id", rule_id)
            logger.debug("Seeded rule: %s", rule_id)

        logger.debug("Database initialized: %s", self._settings.database_path)

    def _get_seeded_rule_id(self) -> str | None:
        from evomind.persistence.seed import Seed

        conn = self._database.connection
        return Seed.seed_default_rule(conn, self._settings)

    def _register_core_services(self) -> None:
        from evomind.persistence.repositories.rule_repository import RuleRepository
        from evomind.persistence.repositories.observation_repository import (
            ObservationRepository,
        )
        from evomind.persistence.repositories.evidence_repository import (
            EvidenceRepository,
        )
        from evomind.persistence.repositories.request_context_repository import (
            RequestContextRepository,
        )

        self._registry.register(
            "rule_repository", RuleRepository(self._database)
        )
        self._registry.register(
            "observation_repository", ObservationRepository(self._database)
        )
        self._registry.register(
            "evidence_repository", EvidenceRepository(self._database)
        )
        self._registry.register(
            "request_context_repository", RequestContextRepository(self._database)
        )

        logger.debug("Core services registered")

    def _emit_startup_trace(self) -> None:
        if not self._settings.is_telemetry_enabled:
            return

        tracer = self._tracer_manager.tracer
        startup_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_SYSTEM_STARTUP,
            attributes={
                "app.name": self._settings.app_name,
                "app.version": self._settings.app_version,
                "schema.version": self._settings.schema_version,
                "telemetry.version": self._settings.telemetry_version,
            },
        )

        rule_id = self._registry.resolve("seeded_rule_id")
        rule_span = SpanHelper.create_span(
            tracer,
            SpanHelper.SPAN_NAME_RULE_CREATED,
            parent=startup_span,
            attributes={
                "rule.id": rule_id,
                "rule.name": "use_parameterized_sql",
                "rule.status.initial": "candidate",
                "rule.confidence.initial": 0.5,
                "rule.alpha.initial": self._settings.rule_initial_alpha,
                "rule.beta.initial": self._settings.rule_initial_beta,
                "threshold.promotion": self._settings.rule_promotion_threshold,
                "threshold.demotion": self._settings.rule_demotion_threshold,
                "threshold.min_evidence": self._settings.rule_min_evidence,
            },
        )
        SpanHelper.end_span(rule_span)
        SpanHelper.end_span(startup_span)

        logger.debug("Startup trace emitted")
