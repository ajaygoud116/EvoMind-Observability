from __future__ import annotations

from evomind.models.behavioral_rule import BehavioralRule
from evomind.models.observation import Observation
from evomind.models.evidence_record import EvidenceRecord
from evomind.models.evaluation_result import EvaluationResult
from evomind.models.request_context import RequestContext
from evomind.models.learning_state import LearningState
from evomind.models.enums import RuleStatus, EvidenceType, Classification


class TestBehavioralRule:
    def test_default_values(self) -> None:
        r = BehavioralRule()
        assert r.status == RuleStatus.CANDIDATE
        assert r.confidence == 0.5
        assert r.alpha == 1.0
        assert r.beta == 1.0
        assert r.promotion_threshold == 0.75
        assert r.demotion_threshold == 0.35
        assert r.min_evidence == 3
        assert r.supporting_count == 0
        assert r.contradicting_count == 0

    def test_total_evidence(self) -> None:
        r = BehavioralRule(supporting_count=3, contradicting_count=2)
        assert r.total_evidence == 5
        r2 = BehavioralRule()
        assert r2.total_evidence == 0

    def test_should_promote(self) -> None:
        r = BehavioralRule(
            status=RuleStatus.CANDIDATE,
            confidence=0.80,
            supporting_count=3,
        )
        assert r.should_promote is True

    def test_should_not_promote_low_confidence(self) -> None:
        r = BehavioralRule(
            status=RuleStatus.CANDIDATE,
            confidence=0.60,
            supporting_count=3,
        )
        assert r.should_promote is False

    def test_should_not_promote_low_evidence(self) -> None:
        r = BehavioralRule(
            status=RuleStatus.CANDIDATE,
            confidence=0.80,
            supporting_count=1,
        )
        assert r.should_promote is False

    def test_should_not_promote_wrong_status(self) -> None:
        r = BehavioralRule(
            status=RuleStatus.ACTIVE,
            confidence=0.80,
            supporting_count=3,
        )
        assert r.should_promote is False

    def test_should_demote(self) -> None:
        r = BehavioralRule(
            status=RuleStatus.ACTIVE,
            confidence=0.30,
        )
        assert r.should_demote is True

    def test_should_not_demote_above_threshold(self) -> None:
        r = BehavioralRule(
            status=RuleStatus.ACTIVE,
            confidence=0.50,
        )
        assert r.should_demote is False

    def test_should_not_demote_wrong_status(self) -> None:
        r = BehavioralRule(
            status=RuleStatus.CANDIDATE,
            confidence=0.30,
        )
        assert r.should_demote is False

    def test_should_re_promote(self) -> None:
        r = BehavioralRule(
            status=RuleStatus.SUSPENDED,
            confidence=0.80,
        )
        assert r.should_re_promote is True

    def test_to_dict_roundtrip(self) -> None:
        r1 = BehavioralRule(
            name="test_rule",
            guidance_text="test guidance",
            confidence=0.75,
            alpha=2.0,
            supporting_count=3,
        )
        data = r1.to_dict()
        r2 = BehavioralRule.from_dict(data)
        assert r2.id == r1.id
        assert r2.name == r1.name
        assert r2.confidence == r1.confidence
        assert r2.alpha == r1.alpha
        assert r2.supporting_count == r1.supporting_count
        assert r2.status == r1.status


class TestObservation:
    def test_default_values(self) -> None:
        o = Observation()
        assert o.classification == Classification.AMBIGUOUS
        assert o.evidence_type == EvidenceType.NEUTRAL

    def test_to_dict_roundtrip(self) -> None:
        o1 = Observation(
            request_id="req-1",
            rule_id="rule-1",
            classification=Classification.UNSAFE,
            evidence_type=EvidenceType.SUPPORTING,
            sql_generated="SELECT * FROM users WHERE id = 123",
            evaluation_reason="literal in WHERE",
        )
        data = o1.to_dict()
        o2 = Observation.from_dict(data)
        assert o2.id == o1.id
        assert o2.classification == o1.classification
        assert o2.evidence_type == o1.evidence_type
        assert o2.sql_generated == o1.sql_generated


class TestEvidenceRecord:
    def test_default_values(self) -> None:
        e = EvidenceRecord()
        assert e.delta == 0.0

    def test_to_dict_roundtrip(self) -> None:
        e1 = EvidenceRecord(
            observation_id="obs-1",
            rule_id="rule-1",
            evidence_type=EvidenceType.SUPPORTING,
            confidence_before=0.5,
            confidence_after=0.67,
            delta=0.17,
        )
        data = e1.to_dict()
        e2 = EvidenceRecord.from_dict(data)
        assert e2.id == e1.id
        assert e2.confidence_before == 0.5
        assert e2.confidence_after == 0.67
        assert e2.delta == 0.17


class TestEvaluationResult:
    def test_default_values(self) -> None:
        e = EvaluationResult()
        assert e.classification == Classification.AMBIGUOUS
        assert e.evaluator_confidence == 1.0
        assert e.detected_patterns == []


class TestRequestContext:
    def test_default_values(self) -> None:
        ctx = RequestContext()
        assert ctx.rule_retrieved is False
        assert ctx.prompt == ""

    def test_to_dict_roundtrip(self) -> None:
        ctx1 = RequestContext(
            prompt="show users",
            sql_generated="SELECT * FROM users",
            rule_retrieved=True,
            rule_retrieved_id="rule-1",
            guidance_injected="use ?",
            trace_id="trace-abc",
        )
        data = ctx1.to_dict()
        ctx2 = RequestContext.from_dict(data)
        assert ctx2.id == ctx1.id
        assert ctx2.rule_retrieved is True
        assert ctx2.prompt == "show users"
        assert ctx2.trace_id == "trace-abc"

    def test_rule_retrieved_boolean_conversion(self) -> None:
        ctx = RequestContext.from_dict({
            "id": "test",
            "prompt": "test",
            "rule_retrieved": 1,
            "created_at": "2024-01-01T00:00:00",
        })
        assert ctx.rule_retrieved is True

        ctx2 = RequestContext.from_dict({
            "id": "test2",
            "prompt": "test",
            "rule_retrieved": 0,
            "created_at": "2024-01-01T00:00:00",
        })
        assert ctx2.rule_retrieved is False


class TestLearningState:
    def test_default_values(self) -> None:
        s = LearningState()
        assert s.confidence == 0.0
        assert s.total_evidence == 0


class TestEnums:
    def test_rule_status_values(self) -> None:
        assert RuleStatus.CANDIDATE.value == "candidate"
        assert RuleStatus.ACTIVE.value == "active"
        assert RuleStatus.SUSPENDED.value == "suspended"
        assert RuleStatus.ARCHIVED.value == "archived"

    def test_evidence_type_values(self) -> None:
        assert EvidenceType.SUPPORTING.value == "supporting"
        assert EvidenceType.CONTRADICTING.value == "contradicting"
        assert EvidenceType.BASELINE.value == "baseline"
        assert EvidenceType.NEUTRAL.value == "neutral"

    def test_classification_values(self) -> None:
        assert Classification.SAFE.value == "safe"
        assert Classification.UNSAFE.value == "unsafe"
        assert Classification.AMBIGUOUS.value == "ambiguous"
