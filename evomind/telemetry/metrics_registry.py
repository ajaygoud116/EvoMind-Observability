from __future__ import annotations

from typing import Iterable

from opentelemetry.metrics import CallbackOptions, Meter, Observation


class MetricsRegistry:
    """Holds metric instruments and provides callbacks for observable gauges.

    Registered instruments:
      - evomind.requests.total (Counter)
      - evomind.sql.safety.ratio (ObservableGauge)
      - evomind.rule.confidence (ObservableGauge)
      - evomind.rule.evidence.count (ObservableGauge)
    """

    def __init__(self, meter: Meter) -> None:
        self._safety_counts: dict[str, int] = {"safe": 0, "unsafe": 0, "ambiguous": 0}
        self._current_confidence: float = 0.5
        self._current_evidence_count: int = 0
        self._current_rule_id: str | None = None

        self.requests_total = meter.create_counter(
            name="evomind.requests.total",
            unit="requests",
            description="Total number of requests processed",
        )

        self.sql_safety_ratio = meter.create_observable_gauge(
            name="evomind.sql.safety.ratio",
            description="Ratio of safe SQL queries",
            callbacks=[self._observe_safety_ratio],
        )

        self.rule_confidence = meter.create_observable_gauge(
            name="evomind.rule.confidence",
            description="Current rule confidence",
            callbacks=[self._observe_rule_confidence],
        )

        self.rule_evidence_count = meter.create_observable_gauge(
            name="evomind.rule.evidence.count",
            description="Total evidence count for current rule",
            callbacks=[self._observe_evidence_count],
        )

    def _observe_safety_ratio(
        self, _options: CallbackOptions
    ) -> Iterable[Observation]:
        total = sum(self._safety_counts.values())
        ratio = self._safety_counts["safe"] / total if total > 0 else 0.0
        yield Observation(ratio)

    def _observe_rule_confidence(
        self, _options: CallbackOptions
    ) -> Iterable[Observation]:
        yield Observation(
            self._current_confidence,
            {"rule.id": self._current_rule_id or ""},
        )

    def _observe_evidence_count(
        self, _options: CallbackOptions
    ) -> Iterable[Observation]:
        yield Observation(
            self._current_evidence_count,
            {"rule.id": self._current_rule_id or ""},
        )

    def record_request(self, classification: str) -> None:
        self.requests_total.add(1, {"classification": classification})
        self._safety_counts[classification] = self._safety_counts.get(classification, 0) + 1

    def record_confidence(self, rule_id: str, confidence: float) -> None:
        self._current_rule_id = rule_id
        self._current_confidence = confidence

    def record_evidence_count(self, rule_id: str, count: int) -> None:
        self._current_rule_id = rule_id
        self._current_evidence_count = count
