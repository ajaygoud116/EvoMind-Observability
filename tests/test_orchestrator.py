from __future__ import annotations

import pytest

from evomind.config.settings import Settings
from evomind.exceptions.errors import OrchestrationError
from evomind.orchestration.lifecycle import LifecycleManager
from evomind.orchestration.orchestrator import Orchestrator


class TestOrchestratorProcessRequest:
    def setup_method(self) -> None:
        self.settings = Settings(database_path=":memory:", otel_enabled=False)
        self.lifecycle = LifecycleManager(self.settings)
        self.registry = self.lifecycle.startup()
        self.orchestrator = Orchestrator(self.registry)

    def teardown_method(self) -> None:
        self.lifecycle.shutdown()

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

    def test_process_request_rule_retrieved(self) -> None:
        result = self.orchestrator.process_request("get users")
        assert result["rule_retrieved"] is True
        assert result["rule_name"] is not None

    def test_process_request_no_guidance(self) -> None:
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
