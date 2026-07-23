from __future__ import annotations

import uuid

import pytest

from evomind.config.settings import Settings
from evomind.learning.evidence_store import EvidenceStore
from evomind.models.enums import Classification, EvidenceType
from evomind.models.observation import Observation
from evomind.models.request_context import RequestContext
from evomind.persistence.database import Database
from evomind.persistence.repositories.observation_repository import (
    ObservationRepository,
)
from evomind.persistence.repositories.request_context_repository import (
    RequestContextRepository,
)
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
def ctx_id(database: Database, seeded_rule_id: str) -> str:
    ctx_repo = RequestContextRepository(database)
    ctx = RequestContext(prompt="test prompt")
    ctx_repo.save(ctx)
    return ctx.id


@pytest.fixture
def obs_id(database: Database, seeded_rule_id: str, ctx_id: str) -> str:
    obs_repo = ObservationRepository(database)
    obs = Observation(
        request_id=ctx_id,
        rule_id=seeded_rule_id,
        classification=Classification.UNSAFE,
        evidence_type=EvidenceType.SUPPORTING,
    )
    obs_repo.save(obs)
    return obs.id


class TestEvidenceStore:
    def test_append_returns_record(
        self,
        evidence_store: EvidenceStore,
        seeded_rule_id: str,
        ctx_id: str,
        obs_id: str,
    ) -> None:
        observation = _make_observation(seeded_rule_id, EvidenceType.SUPPORTING, ctx_id, obs_id)
        record = evidence_store.append(observation, 0.5, 0.6)
        assert record.id is not None
        assert record.observation_id == obs_id
        assert record.rule_id == seeded_rule_id
        assert record.evidence_type == EvidenceType.SUPPORTING
        assert record.confidence_before == 0.5
        assert record.confidence_after == 0.6
        assert record.delta == pytest.approx(0.1)

    def test_append_with_different_types(
        self,
        evidence_store: EvidenceStore,
        seeded_rule_id: str,
        ctx_id: str,
        obs_id: str,
    ) -> None:
        for etype in EvidenceType:
            obs = _make_observation(seeded_rule_id, etype, ctx_id, obs_id)
            record = evidence_store.append(obs, 0.5, 0.6)
            assert record.evidence_type == etype

    def test_append_persists_to_database(
        self,
        evidence_store: EvidenceStore,
        database: Database,
        seeded_rule_id: str,
        ctx_id: str,
        obs_id: str,
    ) -> None:
        observation = _make_observation(seeded_rule_id, EvidenceType.SUPPORTING, ctx_id, obs_id)
        record = evidence_store.append(observation, 0.5, 0.6)
        rows = database.fetch_all(
            "SELECT * FROM evidence_records WHERE id = ?", (record.id,)
        )
        assert len(rows) == 1
        assert rows[0]["id"] == record.id
        assert rows[0]["rule_id"] == seeded_rule_id

    def test_get_summary(
        self,
        evidence_store: EvidenceStore,
        seeded_rule_id: str,
        ctx_id: str,
        obs_id: str,
    ) -> None:
        ctype = EvidenceType.CONTRADICTING
        stype = EvidenceType.SUPPORTING
        for etype in [stype, stype, ctype]:
            obs = _make_observation(seeded_rule_id, etype, ctx_id, obs_id)
            evidence_store.append(obs, 0.5, 0.5)

        summary = evidence_store.get_summary(seeded_rule_id)
        assert summary is not None
        assert summary.get("supporting", 0) == 2
        assert summary.get("contradicting", 0) == 1

    def test_get_confidence_history(
        self,
        evidence_store: EvidenceStore,
        seeded_rule_id: str,
        ctx_id: str,
        obs_id: str,
    ) -> None:
        obs1 = _make_observation(seeded_rule_id, EvidenceType.SUPPORTING, ctx_id, obs_id)
        obs2 = _make_observation(seeded_rule_id, EvidenceType.CONTRADICTING, ctx_id, obs_id)
        evidence_store.append(obs1, 0.5, 0.6)
        evidence_store.append(obs2, 0.6, 0.5)

        history = evidence_store.get_confidence_history(seeded_rule_id)
        assert len(history) == 2

    def test_get_summary_no_evidence(self, evidence_store: EvidenceStore) -> None:
        summary = evidence_store.get_summary("nonexistent-rule")
        assert summary == {
            "supporting": None,
            "contradicting": None,
            "baseline": None,
            "neutral": None,
        }

    def test_get_confidence_history_no_evidence(self, evidence_store: EvidenceStore) -> None:
        history = evidence_store.get_confidence_history("nonexistent-rule")
        assert history == []


def _make_observation(
    rule_id: str,
    evidence_type: EvidenceType,
    request_id: str,
    obs_id: str,
) -> Observation:
    return Observation(
        id=obs_id,
        request_id=request_id,
        rule_id=rule_id,
        sql_generated="SELECT * FROM users",
        classification=Classification.UNSAFE,
        evidence_type=evidence_type,
        evaluation_reason="test",
        created_at="2026-01-01T00:00:00+00:00",
    )
