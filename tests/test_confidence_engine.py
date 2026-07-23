from __future__ import annotations

import pytest

from evomind.config.settings import Settings
from evomind.exceptions.errors import ConfidenceError
from evomind.learning.confidence_engine import ConfidenceEngine
from evomind.models.enums import EvidenceType, RuleStatus
from evomind.persistence.database import Database
from evomind.persistence.repositories.rule_repository import RuleRepository
from evomind.persistence.seed import Seed


@pytest.fixture(autouse=True)
def _reset_db(database: Database) -> None:
    database.reset()


@pytest.fixture
def seeded_rule_id(database: Database, settings: Settings) -> str:
    conn = database.connection
    rule_id = Seed.seed_default_rule(conn, settings)
    assert rule_id is not None
    return rule_id


@pytest.fixture
def rule_repo(database: Database) -> RuleRepository:
    return RuleRepository(database)


@pytest.fixture
def engine(rule_repo: RuleRepository) -> ConfidenceEngine:
    return ConfidenceEngine(rule_repo)


class TestConfidenceEngineUpdate:
    def test_supporting_increases_alpha(self, engine: ConfidenceEngine, rule_repo: RuleRepository, seeded_rule_id: str) -> None:
        rule = rule_repo.get_by_id(seeded_rule_id)
        alpha_before = rule.alpha

        result = engine.update(seeded_rule_id, EvidenceType.SUPPORTING)

        assert result["alpha"] == alpha_before + 1.0
        assert result["beta"] == rule.beta
        assert result["confidence_after"] > result["confidence_before"]
        assert result["evidence_type"] == "supporting"
        assert result["status_changed"] is False

    def test_contradicting_increases_beta(self, engine: ConfidenceEngine, rule_repo: RuleRepository, seeded_rule_id: str) -> None:
        rule = rule_repo.get_by_id(seeded_rule_id)
        beta_before = rule.beta

        result = engine.update(seeded_rule_id, EvidenceType.CONTRADICTING)

        assert result["beta"] == beta_before + 1.0
        assert result["alpha"] == rule.alpha
        assert result["confidence_after"] < result["confidence_before"]
        assert result["evidence_type"] == "contradicting"

    def test_baseline_no_change(self, engine: ConfidenceEngine, rule_repo: RuleRepository, seeded_rule_id: str) -> None:
        rule = rule_repo.get_by_id(seeded_rule_id)
        alpha_before = rule.alpha
        beta_before = rule.beta
        conf_before = rule.confidence

        result = engine.update(seeded_rule_id, EvidenceType.BASELINE)

        assert result["alpha"] == alpha_before
        assert result["beta"] == beta_before
        assert result["confidence_after"] == conf_before
        assert result["delta"] == 0.0

    def test_neutral_no_change(self, engine: ConfidenceEngine, rule_repo: RuleRepository, seeded_rule_id: str) -> None:
        rule = rule_repo.get_by_id(seeded_rule_id)
        alpha_before = rule.alpha
        beta_before = rule.beta
        conf_before = rule.confidence

        result = engine.update(seeded_rule_id, EvidenceType.NEUTRAL)

        assert result["alpha"] == alpha_before
        assert result["beta"] == beta_before
        assert result["confidence_after"] == conf_before
        assert result["delta"] == 0.0

    def test_unknown_rule_id_raises_error(self, engine: ConfidenceEngine) -> None:
        with pytest.raises(ConfidenceError, match="Rule not found"):
            engine.update("nonexistent", EvidenceType.SUPPORTING)


class TestConfidenceEngineStateTransitions:
    def test_candidate_promotes_to_active(self, engine: ConfidenceEngine, rule_repo: RuleRepository, seeded_rule_id: str) -> None:
        rule = rule_repo.get_by_id(seeded_rule_id)
        assert rule.status == RuleStatus.CANDIDATE

        result = engine.update(seeded_rule_id, EvidenceType.SUPPORTING)
        assert result["status_changed"] is False, "Needs 3 evidence"

        result = engine.update(seeded_rule_id, EvidenceType.SUPPORTING)
        assert result["status_changed"] is False, "Needs 3 evidence"

        result = engine.update(seeded_rule_id, EvidenceType.SUPPORTING)
        assert result["status_changed"] is True
        assert result["to_status"] == "active"
        assert result["from_status"] == "candidate"

        rule = rule_repo.get_by_id(seeded_rule_id)
        assert rule.status == RuleStatus.ACTIVE

    def test_active_demotes_to_suspended(self, engine: ConfidenceEngine, rule_repo: RuleRepository, seeded_rule_id: str) -> None:
        self._promote_to_active(engine, rule_repo, seeded_rule_id)

        result = engine.update(seeded_rule_id, EvidenceType.CONTRADICTING)
        assert result["status_changed"] is False

        rule = rule_repo.get_by_id(seeded_rule_id)
        conf = rule.confidence
        contradicts = 0
        while rule.status == RuleStatus.ACTIVE and contradicts < 20:
            engine.update(seeded_rule_id, EvidenceType.CONTRADICTING)
            contradicts += 1
            rule = rule_repo.get_by_id(seeded_rule_id)

        assert rule.status == RuleStatus.SUSPENDED, (
            f"Expected SUSPENDED, got {rule.status.value} "
            f"(confidence={rule.confidence:.4f} after {contradicts} contradicts)"
        )

    def test_suspended_re_promotes_to_active(self, engine: ConfidenceEngine, rule_repo: RuleRepository, seeded_rule_id: str) -> None:
        self._promote_to_active(engine, rule_repo, seeded_rule_id)

        contradicts = 0
        while True:
            rule = rule_repo.get_by_id(seeded_rule_id)
            if rule.status == RuleStatus.SUSPENDED:
                break
            engine.update(seeded_rule_id, EvidenceType.CONTRADICTING)
            contradicts += 1
            if contradicts > 20:
                break

        rule = rule_repo.get_by_id(seeded_rule_id)
        assert rule.status == RuleStatus.SUSPENDED, (
            f"Failed to demote after {contradicts} contradicts "
            f"(confidence={rule.confidence:.4f})"
        )

        supports = 0
        while True:
            rule = rule_repo.get_by_id(seeded_rule_id)
            if rule.status == RuleStatus.ACTIVE:
                break
            engine.update(seeded_rule_id, EvidenceType.SUPPORTING)
            supports += 1
            if supports > 30:
                break

        rule = rule_repo.get_by_id(seeded_rule_id)
        assert rule.status == RuleStatus.ACTIVE, (
            f"Failed to re-promote after {supports} supports "
            f"(confidence={rule.confidence:.4f})"
        )

    def _promote_to_active(
        self, engine: ConfidenceEngine, rule_repo: RuleRepository, rule_id: str
    ) -> None:
        for _ in range(3):
            engine.update(rule_id, EvidenceType.SUPPORTING)
        rule = rule_repo.get_by_id(rule_id)
        assert rule.status == RuleStatus.ACTIVE
