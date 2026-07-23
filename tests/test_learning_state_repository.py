from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from evomind.config.settings import Settings
from evomind.models.learning_state import LearningState
from evomind.models.request_context import RequestContext
from evomind.persistence.database import Database
from evomind.persistence.repositories.learning_state_repository import (
    LearningStateRepository,
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
def repo(database: Database) -> LearningStateRepository:
    return LearningStateRepository(database)


@pytest.fixture
def ctx_id(database: Database) -> str:
    ctx_repo = RequestContextRepository(database)
    ctx = RequestContext(prompt="test")
    ctx_repo.save(ctx)
    return ctx.id


def _make_state(rule_id: str, request_id: str | None = None) -> LearningState:
    return LearningState(
        id=str(uuid4()),
        request_id=request_id or str(uuid4()),
        rule_id=rule_id,
        confidence=0.75,
        status="active",
        supporting_count=5,
        contradicting_count=2,
        total_evidence=7,
        snapshot_at=datetime.now(timezone.utc).isoformat(),
    )


class TestLearningStateRepository:
    def test_save_and_get_by_rule_id(
        self, repo: LearningStateRepository, seeded_rule_id: str, ctx_id: str
    ) -> None:
        state = _make_state(seeded_rule_id, request_id=ctx_id)
        repo.save(state)
        results = repo.get_by_rule_id(seeded_rule_id)
        assert len(results) == 1
        assert results[0].id == state.id
        assert results[0].confidence == 0.75
        assert results[0].status == "active"

    def test_get_by_rule_id_ordered_by_snapshot_desc(
        self, repo: LearningStateRepository, seeded_rule_id: str, ctx_id: str
    ) -> None:
        s1 = _make_state(seeded_rule_id, request_id=ctx_id)
        s2 = _make_state(seeded_rule_id, request_id=ctx_id)
        repo.save(s1)
        repo.save(s2)
        results = repo.get_by_rule_id(seeded_rule_id)
        assert len(results) >= 2
        assert results[0].snapshot_at >= results[-1].snapshot_at

    def test_get_by_request_id(
        self, repo: LearningStateRepository, seeded_rule_id: str, ctx_id: str
    ) -> None:
        s1 = _make_state(seeded_rule_id, request_id=ctx_id)
        s2 = _make_state(seeded_rule_id, request_id=ctx_id)
        repo.save(s1)
        repo.save(s2)
        results = repo.get_by_request_id(ctx_id)
        assert len(results) == 2

    def test_get_by_rule_id_empty(self, repo: LearningStateRepository) -> None:
        assert repo.get_by_rule_id("nonexistent") == []

    def test_get_by_request_id_empty(self, repo: LearningStateRepository) -> None:
        assert repo.get_by_request_id("nonexistent") == []

    def test_save_persists_all_fields(
        self, repo: LearningStateRepository, seeded_rule_id: str, ctx_id: str
    ) -> None:
        state = _make_state(seeded_rule_id, request_id=ctx_id)
        repo.save(state)
        results = repo.get_by_rule_id(seeded_rule_id)
        saved = results[0]
        assert saved.id == state.id
        assert saved.rule_id == state.rule_id
        assert saved.request_id == state.request_id
        assert saved.confidence == state.confidence
        assert saved.status == state.status
        assert saved.supporting_count == state.supporting_count
        assert saved.contradicting_count == state.contradicting_count
        assert saved.total_evidence == state.total_evidence
        assert saved.snapshot_at == state.snapshot_at
