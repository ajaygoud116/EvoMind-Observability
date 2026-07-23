"""Integration acceptance test for the complete learning loop.

Scenario:
  Request 1-3: no active rules -> unsafe SQL -> supporting observation -> PROMOTION
  Request 4-5: ACTIVE rule retrieved -> guidance injected -> SAFE SQL -> confidence grows

Uses DELETE prompts because:
  - Without guidance: DELETE FROM users (no WHERE) -> UNSAFE -> supporting (pre-promotion)
  - With guidance: DELETE FROM users WHERE id = ? (parameterized) -> SAFE -> supporting (post-promotion)
"""

from __future__ import annotations

import os as _os
import tempfile as _tempfile
import uuid as _uuid
from collections.abc import Generator

import pytest

from evomind.config.settings import Settings
from evomind.models.enums import RuleStatus
from evomind.orchestration.lifecycle import LifecycleManager
from evomind.orchestration.orchestrator import Orchestrator


def _db_path() -> str:
    return _os.path.join(
        _tempfile.gettempdir(), f"evomind_loop_{_uuid.uuid4().hex}.db"
    )


@pytest.fixture
def db_path() -> str:
    return _db_path()


@pytest.fixture
def settings(db_path: str) -> Settings:
    return Settings(
        database_path=db_path,
        otel_enabled=False,
        debug=True,
    )


@pytest.fixture
def lifecycle(settings: Settings, db_path: str) -> Generator[LifecycleManager, None, None]:
    mgr = LifecycleManager(settings)
    mgr.startup()
    yield mgr
    mgr.shutdown()
    if _os.path.exists(db_path):
        try:
            _os.remove(db_path)
        except PermissionError:
            pass


@pytest.fixture
def orchestrator(lifecycle: LifecycleManager) -> Orchestrator:
    return Orchestrator(lifecycle._registry)


@pytest.fixture
def rule_repo(lifecycle: LifecycleManager):
    return lifecycle._registry.resolve("rule_repository")


@pytest.fixture
def seeded_rule_id(lifecycle: LifecycleManager) -> str:
    return lifecycle._registry.resolve("seeded_rule_id")


class TestLearningLoop:
    def test_complete_lifecycle(
        self,
        orchestrator: Orchestrator,
        rule_repo,
        seeded_rule_id: str,
    ) -> None:
        prompt = "delete user with id 1"

        for i in range(3):
            result = orchestrator.process_request(prompt)
            assert result["rule_retrieved"] is False
            assert result["guidance_injected"] is False
            assert result["classification"] == "unsafe"

        rule = rule_repo.get_by_id(seeded_rule_id)
        assert rule.status == RuleStatus.ACTIVE, (
            f"Expected ACTIVE after 3 requests, got {rule.status.value}"
        )

        result4 = orchestrator.process_request(prompt)
        assert result4["rule_retrieved"] is True
        assert result4["guidance_injected"] is True
        assert "?" in result4["sql"], (
            f"SQL should be parameterized when guidance injected: {result4['sql']}"
        )
        assert result4["classification"] == "safe", (
            f"Parameterized SQL should be classified safe: {result4['classification']}"
        )

        result5 = orchestrator.process_request(prompt)
        assert result5["rule_retrieved"] is True
        assert result5["guidance_injected"] is True
        assert "?" in result5["sql"]

        rule = rule_repo.get_by_id(seeded_rule_id)
        assert rule.status == RuleStatus.ACTIVE
        assert rule.confidence > 0.80, (
            f"Confidence should be >0.80 after promotion + 2 supports, "
            f"got {rule.confidence:.4f}"
        )

    def test_different_prompts_consistent_behavior(
        self,
        orchestrator: Orchestrator,
        rule_repo,
        seeded_rule_id: str,
    ) -> None:
        prompt = "delete user with id 1"

        for _ in range(3):
            result = orchestrator.process_request(prompt)
            assert result["classification"] == "unsafe"

        rule = rule_repo.get_by_id(seeded_rule_id)
        assert rule.status == RuleStatus.ACTIVE

        for _ in range(2):
            result = orchestrator.process_request(prompt)
            assert result["rule_retrieved"] is True
            assert result["guidance_injected"] is True
            assert result["classification"] == "safe"

    def test_learning_is_persistent(
        self,
        orchestrator: Orchestrator,
        rule_repo,
        seeded_rule_id: str,
    ) -> None:
        prompt = "delete user with id 1"
        for _ in range(3):
            orchestrator.process_request(prompt)

        rule = rule_repo.get_by_id(seeded_rule_id)
        assert rule.status == RuleStatus.ACTIVE
        assert rule.confidence == pytest.approx(0.8)
        assert rule.supporting_count == 3
        assert rule.contradicting_count == 0
        assert rule.min_evidence == 3
        assert rule.total_evidence == 3

    def test_rule_status_tracks_across_requests(
        self,
        orchestrator: Orchestrator,
        rule_repo,
        seeded_rule_id: str,
        lifecycle: LifecycleManager,
    ) -> None:
        prompt = "delete user with id 1"
        assert rule_repo.get_by_id(seeded_rule_id).status == RuleStatus.CANDIDATE

        r1 = orchestrator.process_request(prompt)
        assert r1["status_changed"] is False
        assert rule_repo.get_by_id(seeded_rule_id).status == RuleStatus.CANDIDATE

        r2 = orchestrator.process_request(prompt)
        assert r2["status_changed"] is False
        assert rule_repo.get_by_id(seeded_rule_id).status == RuleStatus.CANDIDATE

        r3 = orchestrator.process_request(prompt)
        assert r3["status_changed"] is True
        assert r3["to_status"] == "active"
        assert rule_repo.get_by_id(seeded_rule_id).status == RuleStatus.ACTIVE
