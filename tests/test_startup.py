from __future__ import annotations

import os as _os
import tempfile as _tempfile
import uuid as _uuid
from unittest.mock import patch

from evomind.config.settings import Settings
from evomind.orchestration.lifecycle import LifecycleManager
from evomind.orchestration.service_registry import ServiceRegistry


def _db() -> str:
    return _os.path.join(
        _tempfile.gettempdir(), f"evomind_startup_{_uuid.uuid4().hex}.db"
    )


class TestStartup:
    def test_startup_creates_registry(self) -> None:
        p = _db()
        settings = Settings(database_path=p, otel_enabled=False)
        lifecycle = LifecycleManager(settings)
        registry = lifecycle.startup()

        assert isinstance(registry, ServiceRegistry)
        assert registry.is_registered("database")
        assert registry.is_registered("tracer_manager")
        assert registry.is_registered("meter_manager")
        assert registry.is_registered("seeded_rule_id")
        assert registry.is_registered("rule_repository")
        assert registry.is_registered("observation_repository")
        assert registry.is_registered("evidence_repository")
        assert registry.is_registered("request_context_repository")

        lifecycle.shutdown()
        _clean(p)

    def test_startup_seeds_rule(self) -> None:
        p = _db()
        settings = Settings(database_path=p, otel_enabled=False)
        lifecycle = LifecycleManager(settings)
        registry = lifecycle.startup()

        rule_id = registry.resolve("seeded_rule_id")
        assert rule_id is not None
        assert isinstance(rule_id, str)
        assert len(rule_id) > 0

        rule_repo = registry.resolve("rule_repository")
        rule = rule_repo.get_by_id(rule_id)
        assert rule is not None
        assert rule.name == "use_parameterized_sql"
        assert rule.status.value == "candidate"

        lifecycle.shutdown()
        _clean(p)

    def test_startup_idempotent(self) -> None:
        p = _db()
        settings = Settings(database_path=p, otel_enabled=False)
        lifecycle = LifecycleManager(settings)
        registry1 = lifecycle.startup()
        rule_id1 = registry1.resolve("seeded_rule_id")
        lifecycle.shutdown()

        lifecycle2 = LifecycleManager(settings)
        registry2 = lifecycle2.startup()
        rule_id2 = registry2.resolve("seeded_rule_id")

        assert rule_id2 is not None
        lifecycle2.shutdown()
        _clean(p)

    def test_shutdown_clean(self) -> None:
        p = _db()
        settings = Settings(database_path=p, otel_enabled=False)
        lifecycle = LifecycleManager(settings)
        lifecycle.startup()
        lifecycle.shutdown()
        _clean(p)

    def test_telemetry_enabled_startup(self, in_memory_exporter) -> None:
        import opentelemetry.trace as trace_module

        p = _db()
        settings = Settings(database_path=p, otel_enabled=True)
        lifecycle = LifecycleManager(settings)

        from evomind.telemetry.tracer import TracerManager

        tracer_mgr = TracerManager(settings)
        tracer_mgr._exporter = in_memory_exporter
        lifecycle._tracer_manager = tracer_mgr

        def _force_set(provider):
            trace_module._TRACER_PROVIDER = provider

        with patch.object(trace_module, "set_tracer_provider", _force_set):
            lifecycle.startup()

        if lifecycle._tracer_manager.provider:
            lifecycle._tracer_manager.provider.force_flush()
        spans = in_memory_exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "evomind.system.startup" in span_names
        assert "evomind.rule.created" in span_names

        lifecycle.shutdown()
        _clean(p)

    def test_registry_contains_all_services(self) -> None:
        p = _db()
        settings = Settings(database_path=p, otel_enabled=False)
        lifecycle = LifecycleManager(settings)
        registry = lifecycle.startup()

        expected_keys = {
            "tracer_manager",
            "meter_manager",
            "database",
            "seeded_rule_id",
            "metrics_registry",
            "rule_repository",
            "observation_repository",
            "evidence_repository",
            "request_context_repository",
        }

        assert set(registry.keys()) == expected_keys
        lifecycle.shutdown()
        _clean(p)


def _clean(p: str) -> None:
    if _os.path.exists(p):
        try:
            _os.remove(p)
        except PermissionError:
            pass
