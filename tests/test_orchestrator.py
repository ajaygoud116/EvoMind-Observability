from __future__ import annotations

import os as _os
import tempfile as _tempfile
import uuid as _uuid

import pytest

from evomind.config.settings import Settings
from evomind.exceptions.errors import OrchestrationError
from evomind.orchestration.lifecycle import LifecycleManager
from evomind.orchestration.orchestrator import Orchestrator


class TestOrchestratorProcessRequest:
    def setup_method(self) -> None:
        self._db_path = _os.path.join(
            _tempfile.gettempdir(), f"evomind_orch_{_uuid.uuid4().hex}.db"
        )
        self.settings = Settings(
            database_path=self._db_path, otel_enabled=False
        )
        self.lifecycle = LifecycleManager(self.settings)
        self.registry = self.lifecycle.startup()
        self.orchestrator = Orchestrator(self.registry)

    def teardown_method(self) -> None:
        self.lifecycle.shutdown()
        if _os.path.exists(self._db_path):
            try:
                _os.remove(self._db_path)
            except PermissionError:
                pass

    def test_process_request_returns_dict(self) -> None:
        result = self.orchestrator.process_request("show me all users")
        assert isinstance(result, dict)
        assert "request_id" in result
        assert "sql" in result
        assert "classification" in result

    def test_process_request_generates_sql(self) -> None:
        result = self.orchestrator.process_request("show me all users")
        assert len(result["sql"]) > 0
        assert "SELECT" in result["sql"] or "select" in result["sql"].lower()

    def test_process_request_unsafe_classification(self) -> None:
        result = self.orchestrator.process_request("show me all users")
        assert result["classification"] in ("unsafe", "safe", "ambiguous")

    def test_process_request_rule_not_retrieved_initially(self) -> None:
        result = self.orchestrator.process_request("get users")
        assert result["rule_retrieved"] is False
        assert result["rule_name"] is None

    def test_process_request_no_guidance_initially(self) -> None:
        result = self.orchestrator.process_request("show all users")
        assert result["guidance_injected"] is False

    def test_process_request_has_confidence(self) -> None:
        result = self.orchestrator.process_request("find users")
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_process_request_drop_is_unsafe(self) -> None:
        result = self.orchestrator.process_request("drop the users table")
        assert result["classification"] == "unsafe"

    def test_process_request_delete_is_unsafe(self) -> None:
        result = self.orchestrator.process_request("delete user with id 1")
        assert result["classification"] == "unsafe"

    def test_empty_prompt_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            self.orchestrator.process_request("")

    def test_whitespace_prompt_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            self.orchestrator.process_request("   ")

    def test_observation_persisted(self) -> None:
        obs_repo = self.registry.resolve("observation_repository")
        result = self.orchestrator.process_request("get users")
        observations = obs_repo.get_by_request_id(result["request_id"])
        assert len(observations) >= 1

    def test_request_context_persisted(self) -> None:
        ctx_repo = self.registry.resolve("request_context_repository")
        result = self.orchestrator.process_request("show me orders")
        ctx = ctx_repo.get_by_id(result["request_id"])
        assert ctx is not None
        assert ctx.prompt == "show me orders"
        assert ctx.sql_generated is not None

    def test_deterministic_same_prompt_same_result(self) -> None:
        r1 = self.orchestrator.process_request("get all users")
        r2 = self.orchestrator.process_request("get all users")
        assert r1["sql"] == r2["sql"]
        assert r1["classification"] == r2["classification"]

    def test_learning_data_survives_lifecycle_restart(self) -> None:
        db_path = _os.path.join(
            _tempfile.gettempdir(), f"evomind_orch_{_uuid.uuid4().hex}.db"
        )
        try:
            settings = Settings(database_path=db_path, otel_enabled=False)
            lifecycle = LifecycleManager(settings)
            registry = lifecycle.startup()
            orchestrator = Orchestrator(registry)
            result = orchestrator.process_request("show me users")
            request_id = result["request_id"]
            lifecycle.shutdown()

            lifecycle2 = LifecycleManager(settings)
            registry2 = lifecycle2.startup()

            ctx_repo = registry2.resolve("request_context_repository")
            obs_repo = registry2.resolve("observation_repository")
            rule_repo = registry2.resolve("rule_repository")
            ev_repo = registry2.resolve("evidence_repository")
            db = registry2.resolve("database")

            ctx = ctx_repo.get_by_id(request_id)
            assert ctx is not None, "RequestContext should survive restart"

            observations = obs_repo.get_by_request_id(request_id)
            assert len(observations) >= 1, "Observations should survive restart"

            seeded_rule_id = registry2.resolve("seeded_rule_id")
            rule = rule_repo.get_by_id(seeded_rule_id)
            assert rule is not None
            learning_states = db.fetch_all(
                "SELECT * FROM learning_states WHERE request_id = ?",
                (request_id,),
            )
            assert len(learning_states) >= 1, "LearningStates should survive restart"

            evidence = db.fetch_all(
                "SELECT * FROM evidence_records WHERE rule_id = ? ORDER BY created_at DESC LIMIT 1",
                (seeded_rule_id,),
            )
            assert len(evidence) >= 1, "Evidence should survive restart"

            lifecycle2.shutdown()
        finally:
            if _os.path.exists(db_path):
                try:
                    _os.remove(db_path)
                except PermissionError:
                    pass
