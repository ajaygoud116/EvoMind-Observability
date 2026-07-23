from __future__ import annotations

import pytest

from evomind.config.settings import Settings
from evomind.telemetry.meter import MeterManager
from evomind.telemetry.metrics_registry import MetricsRegistry


@pytest.fixture
def registry() -> MetricsRegistry:
    settings = Settings(otel_enabled=False)
    mgr = MeterManager(settings)
    mgr.initialize()
    return MetricsRegistry(mgr.meter)


class TestMetricsRegistry:
    def test_instruments_created(self, registry: MetricsRegistry) -> None:
        assert registry.requests_total is not None
        assert registry.sql_safety_ratio is not None
        assert registry.rule_confidence is not None
        assert registry.rule_evidence_count is not None

    def test_record_request_updates_counter(self, registry: MetricsRegistry) -> None:
        registry.record_request("safe")
        registry.record_request("unsafe")
        registry.record_request("ambiguous")
        assert registry._safety_counts["safe"] == 1
        assert registry._safety_counts["unsafe"] == 1
        assert registry._safety_counts["ambiguous"] == 1

    def test_record_request_increments_safety_counts(
        self, registry: MetricsRegistry
    ) -> None:
        registry.record_request("safe")
        registry.record_request("safe")
        assert registry._safety_counts["safe"] == 2

    def test_observe_safety_ratio_no_requests(
        self, registry: MetricsRegistry
    ) -> None:
        observations = list(registry._observe_safety_ratio(None))
        assert len(observations) == 1
        assert observations[0].value == 0.0

    def test_observe_safety_ratio_with_requests(
        self, registry: MetricsRegistry
    ) -> None:
        registry.record_request("safe")
        registry.record_request("unsafe")
        observations = list(registry._observe_safety_ratio(None))
        assert len(observations) == 1
        assert observations[0].value == 0.5

    def test_observe_safety_ratio_all_safe(
        self, registry: MetricsRegistry
    ) -> None:
        registry.record_request("safe")
        registry.record_request("safe")
        observations = list(registry._observe_safety_ratio(None))
        assert len(observations) == 1
        assert observations[0].value == 1.0

    def test_observe_rule_confidence(self, registry: MetricsRegistry) -> None:
        registry.record_confidence("rule-1", 0.85)
        observations = list(registry._observe_rule_confidence(None))
        assert len(observations) == 1
        assert observations[0].value == 0.85
        assert observations[0].attributes == {"rule.id": "rule-1"}

    def test_observe_rule_confidence_default(self, registry: MetricsRegistry) -> None:
        observations = list(registry._observe_rule_confidence(None))
        assert len(observations) == 1
        assert observations[0].value == 0.5
        assert observations[0].attributes == {"rule.id": ""}

    def test_observe_evidence_count(self, registry: MetricsRegistry) -> None:
        registry.record_evidence_count("rule-1", 7)
        observations = list(registry._observe_evidence_count(None))
        assert len(observations) == 1
        assert observations[0].value == 7
        assert observations[0].attributes == {"rule.id": "rule-1"}

    def test_observe_evidence_count_default(self, registry: MetricsRegistry) -> None:
        observations = list(registry._observe_evidence_count(None))
        assert len(observations) == 1
        assert observations[0].value == 0
        assert observations[0].attributes == {"rule.id": ""}

    def test_record_request_then_safety_ratio(
        self, registry: MetricsRegistry
    ) -> None:
        registry.record_request("safe")
        registry.record_request("safe")
        registry.record_request("unsafe")
        observations = list(registry._observe_safety_ratio(None))
        assert observations[0].value == 2.0 / 3.0
