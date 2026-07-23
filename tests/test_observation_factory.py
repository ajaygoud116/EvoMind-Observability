from __future__ import annotations

import pytest

from evomind.models.enums import Classification, EvidenceType
from evomind.models.evaluation_result import EvaluationResult
from evomind.models.request_context import RequestContext
from evomind.observation.observation_factory import ObservationFactory


class TestObservationFactory:
    def setup_method(self) -> None:
        self.factory = ObservationFactory()
        self.rule_id = "test-rule-id"

    def test_pre_promotion_unsafe_to_supporting(self) -> None:
        context = RequestContext(prompt="test", sql_generated="DROP TABLE users")
        evaluation = EvaluationResult(
            classification=Classification.UNSAFE,
            reason="Dangerous DDL",
            detected_patterns=["dangerous_ddl"],
        )
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.evidence_type == EvidenceType.SUPPORTING
        assert obs.classification == Classification.UNSAFE
        assert obs.rule_id == self.rule_id
        assert obs.request_id == context.id

    def test_pre_promotion_safe_to_baseline(self) -> None:
        context = RequestContext(prompt="test", sql_generated="SELECT 1")
        evaluation = EvaluationResult(
            classification=Classification.SAFE,
            reason="No issues",
            detected_patterns=[],
        )
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.evidence_type == EvidenceType.BASELINE
        assert obs.classification == Classification.SAFE

    def test_pre_promotion_ambiguous_to_neutral(self) -> None:
        context = RequestContext(prompt="test")
        evaluation = EvaluationResult(classification=Classification.AMBIGUOUS)
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.evidence_type == EvidenceType.NEUTRAL
        assert obs.classification == Classification.AMBIGUOUS

    def test_post_promotion_safe_to_supporting(self) -> None:
        context = RequestContext(
            prompt="test",
            sql_generated="SELECT * FROM users WHERE id = ?",
            guidance_injected="Use parameterized queries",
        )
        evaluation = EvaluationResult(classification=Classification.SAFE)
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.evidence_type == EvidenceType.SUPPORTING
        assert obs.classification == Classification.SAFE

    def test_post_promotion_unsafe_to_contradicting(self) -> None:
        context = RequestContext(
            prompt="test",
            sql_generated="DROP TABLE users",
            guidance_injected="Use parameterized queries",
        )
        evaluation = EvaluationResult(classification=Classification.UNSAFE)
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.evidence_type == EvidenceType.CONTRADICTING
        assert obs.classification == Classification.UNSAFE

    def test_post_promotion_ambiguous_to_neutral(self) -> None:
        context = RequestContext(
            prompt="test",
            guidance_injected="Use parameterized queries",
        )
        evaluation = EvaluationResult(classification=Classification.AMBIGUOUS)
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.evidence_type == EvidenceType.NEUTRAL

    def test_observation_has_evaluation_metadata(self) -> None:
        context = RequestContext(prompt="test")
        evaluation = EvaluationResult(
            classification=Classification.UNSAFE,
            detected_patterns=["dangerous_ddl"],
            evaluator_confidence=1.0,
        )
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.metadata is not None
        assert obs.metadata["detected_patterns"] == ["dangerous_ddl"]
        assert obs.metadata["evaluator_confidence"] == 1.0

    def test_observation_sql_generated_from_context(self) -> None:
        context = RequestContext(prompt="test", sql_generated="SELECT * FROM users")
        evaluation = EvaluationResult(classification=Classification.UNSAFE)
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.sql_generated == "SELECT * FROM users"

    def test_observation_evaluation_reason_from_result(self) -> None:
        context = RequestContext(prompt="test")
        evaluation = EvaluationResult(
            classification=Classification.UNSAFE,
            reason="Dangerous DDL",
        )
        obs = self.factory.create(evaluation, context, self.rule_id)
        assert obs.evaluation_reason == "Dangerous DDL"

    def test_none_evaluation_raises(self) -> None:
        context = RequestContext(prompt="test")
        with pytest.raises(ValueError, match="must not be None"):
            self.factory.create(None, context, self.rule_id)
