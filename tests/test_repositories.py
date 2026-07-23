from __future__ import annotations

import pytest

from evomind.models.behavioral_rule import BehavioralRule
from evomind.models.observation import Observation
from evomind.models.evidence_record import EvidenceRecord
from evomind.models.request_context import RequestContext
from evomind.models.enums import RuleStatus, EvidenceType, Classification


class TestRuleRepository:
    def test_save_and_get_by_id(self, repositories) -> None:
        repo = repositories["rule_repository"]
        rule = BehavioralRule(name="test_rule", guidance_text="test")
        repo.save(rule)

        fetched = repo.get_by_id(rule.id)
        assert fetched is not None
        assert fetched.name == "test_rule"
        assert fetched.status == RuleStatus.CANDIDATE

    def test_get_by_name(self, repositories) -> None:
        repo = repositories["rule_repository"]
        rule = BehavioralRule(name="unique_rule", guidance_text="g")
        repo.save(rule)

        fetched = repo.get_by_name("unique_rule")
        assert fetched is not None
        assert fetched.id == rule.id

    def test_get_by_name_not_found(self, repositories) -> None:
        repo = repositories["rule_repository"]
        fetched = repo.get_by_name("nonexistent")
        assert fetched is None

    def test_get_active_rules(self, repositories) -> None:
        repo = repositories["rule_repository"]
        r1 = BehavioralRule(name="active1", guidance_text="g", status=RuleStatus.ACTIVE)
        r2 = BehavioralRule(name="candidate1", guidance_text="g", status=RuleStatus.CANDIDATE)
        r3 = BehavioralRule(name="active2", guidance_text="g", status=RuleStatus.ACTIVE)
        repo.save(r1)
        repo.save(r2)
        repo.save(r3)

        active = repo.get_active_rules()
        assert len(active) == 2
        active_names = {r.name for r in active}
        assert "active1" in active_names
        assert "active2" in active_names

    def test_get_all(self, repositories) -> None:
        repo = repositories["rule_repository"]
        repo.save(BehavioralRule(name="r1", guidance_text="g"))
        repo.save(BehavioralRule(name="r2", guidance_text="g"))

        all_rules = repo.get_all()
        assert len(all_rules) >= 2

    def test_update(self, repositories) -> None:
        repo = repositories["rule_repository"]
        rule = BehavioralRule(name="updatable", guidance_text="g", confidence=0.5)
        repo.save(rule)

        rule.confidence = 0.8
        rule.status = RuleStatus.ACTIVE
        repo.update(rule)

        fetched = repo.get_by_id(rule.id)
        assert fetched is not None
        assert fetched.confidence == 0.8
        assert fetched.status == RuleStatus.ACTIVE

    def test_delete(self, repositories) -> None:
        repo = repositories["rule_repository"]
        rule = BehavioralRule(name="deletable", guidance_text="g")
        repo.save(rule)

        repo.delete(rule.id)
        fetched = repo.get_by_id(rule.id)
        assert fetched is None

    def test_count(self, repositories) -> None:
        repo = repositories["rule_repository"]
        initial = repo.count()
        repo.save(BehavioralRule(name="count_test", guidance_text="g"))
        assert repo.count() == initial + 1

    def test_unique_name_constraint(self, repositories) -> None:
        repo = repositories["rule_repository"]
        repo.save(BehavioralRule(name="duplicate", guidance_text="g"))
        with pytest.raises(Exception):
            repo.save(BehavioralRule(name="duplicate", guidance_text="g"))


class TestObservationRepository:
    def _create_rule(self, repo, name="test-rule") -> str:
        rule = BehavioralRule(name=name, guidance_text="test guidance")
        repo.save(rule)
        return rule.id

    def test_save_and_get(self, repositories, database) -> None:
        obs_repo = repositories["observation_repository"]
        ctx_repo = repositories["request_context_repository"]
        rule_repo = repositories["rule_repository"]

        rule_id = self._create_rule(rule_repo)
        ctx = RequestContext(prompt="test")
        ctx_repo.save(ctx)

        obs = Observation(
            request_id=ctx.id,
            rule_id=rule_id,
            classification=Classification.UNSAFE,
            evidence_type=EvidenceType.SUPPORTING,
            sql_generated="SELECT * FROM users",
        )
        obs_repo.save(obs)

        fetched = obs_repo.get_by_id(obs.id)
        assert fetched is not None
        assert fetched.classification == Classification.UNSAFE
        assert fetched.evidence_type == EvidenceType.SUPPORTING

    def test_get_by_request_id(self, repositories, database) -> None:
        obs_repo = repositories["observation_repository"]
        ctx_repo = repositories["request_context_repository"]
        rule_repo = repositories["rule_repository"]

        rule_id = self._create_rule(rule_repo, "r1-rule")
        ctx = RequestContext(prompt="test")
        ctx_repo.save(ctx)

        obs1 = Observation(request_id=ctx.id, rule_id=rule_id)
        obs2 = Observation(request_id=ctx.id, rule_id=rule_id)
        obs_repo.save(obs1)
        obs_repo.save(obs2)

        results = obs_repo.get_by_request_id(ctx.id)
        assert len(results) == 2

    def test_get_by_rule_id(self, repositories, database) -> None:
        obs_repo = repositories["observation_repository"]
        ctx_repo = repositories["request_context_repository"]
        rule_repo = repositories["rule_repository"]

        rule_id_a = self._create_rule(rule_repo, "rule-a")
        rule_id_b = self._create_rule(rule_repo, "rule-b")
        ctx = RequestContext(prompt="test")
        ctx_repo.save(ctx)

        obs1 = Observation(request_id=ctx.id, rule_id=rule_id_a)
        obs2 = Observation(request_id=ctx.id, rule_id=rule_id_a)
        obs3 = Observation(request_id=ctx.id, rule_id=rule_id_b)
        obs_repo.save(obs1)
        obs_repo.save(obs2)
        obs_repo.save(obs3)

        results = obs_repo.get_by_rule_id(rule_id_a)
        assert len(results) == 2


class TestEvidenceRepository:
    def _create_rule(self, repo, name="ev-rule") -> str:
        rule = BehavioralRule(name=name, guidance_text="ev guidance")
        repo.save(rule)
        return rule.id

    def _create_ctx(self, repo) -> str:
        ctx = RequestContext(prompt="ev test")
        repo.save(ctx)
        return ctx.id

    def _create_obs(self, obs_repo, rule_id: str, ctx_id: str, tag="o") -> str:
        obs = Observation(
            request_id=ctx_id,
            rule_id=rule_id,
            classification=Classification.SAFE,
            evidence_type=EvidenceType.SUPPORTING,
        )
        obs_repo.save(obs)
        return obs.id

    def test_save_and_get(self, repositories) -> None:
        ev_repo = repositories["evidence_repository"]
        obs_repo = repositories["observation_repository"]
        rule_repo = repositories["rule_repository"]
        ctx_repo = repositories["request_context_repository"]

        rule_id = self._create_rule(rule_repo)
        ctx_id = self._create_ctx(ctx_repo)
        obs_id = self._create_obs(obs_repo, rule_id, ctx_id)

        ev = EvidenceRecord(
            observation_id=obs_id,
            rule_id=rule_id,
            evidence_type=EvidenceType.SUPPORTING,
            request_id=ctx_id,
            confidence_before=0.5,
            confidence_after=0.67,
            delta=0.17,
        )
        ev_repo.save(ev)

        fetched = ev_repo.get_by_id(ev.id)
        assert fetched is not None
        assert fetched.evidence_type == EvidenceType.SUPPORTING
        assert fetched.confidence_before == 0.5
        assert fetched.confidence_after == 0.67

    def test_get_by_rule_id(self, repositories) -> None:
        ev_repo = repositories["evidence_repository"]
        obs_repo = repositories["observation_repository"]
        rule_repo = repositories["rule_repository"]
        ctx_repo = repositories["request_context_repository"]

        rule_id = self._create_rule(rule_repo, "rule-x")
        ctx_id = self._create_ctx(ctx_repo)

        for i in range(3):
            obs_id = self._create_obs(obs_repo, rule_id, ctx_id, str(i))
            ev = EvidenceRecord(
                observation_id=obs_id,
                rule_id=rule_id,
                evidence_type=EvidenceType.SUPPORTING,
                request_id=ctx_id,
                confidence_before=0.5,
                confidence_after=0.5 + 0.1 * (i + 1),
                delta=0.1 * (i + 1),
            )
            ev_repo.save(ev)

        records = ev_repo.get_by_rule_id(rule_id)
        assert len(records) == 3

    def test_get_summary(self, repositories) -> None:
        ev_repo = repositories["evidence_repository"]
        obs_repo = repositories["observation_repository"]
        rule_repo = repositories["rule_repository"]
        ctx_repo = repositories["request_context_repository"]

        rule_id = self._create_rule(rule_repo, "summary-rule")
        ctx_id = self._create_ctx(ctx_repo)

        types = [
            EvidenceType.SUPPORTING,
            EvidenceType.SUPPORTING,
            EvidenceType.CONTRADICTING,
            EvidenceType.BASELINE,
        ]
        for i, t in enumerate(types):
            obs_id = self._create_obs(obs_repo, rule_id, ctx_id, f"s{i}")
            ev = EvidenceRecord(
                observation_id=obs_id,
                rule_id=rule_id,
                evidence_type=t,
                request_id=ctx_id,
                confidence_before=0.5,
                confidence_after=0.5,
                delta=0.0,
            )
            ev_repo.save(ev)

        summary = ev_repo.get_summary(rule_id)
        assert summary["supporting"] == 2
        assert summary["contradicting"] == 1
        assert summary["baseline"] == 1

    def test_get_confidence_history(self, repositories) -> None:
        ev_repo = repositories["evidence_repository"]
        obs_repo = repositories["observation_repository"]
        rule_repo = repositories["rule_repository"]
        ctx_repo = repositories["request_context_repository"]

        rule_id = self._create_rule(rule_repo, "history-rule")
        ctx_id = self._create_ctx(ctx_repo)

        for i in range(3):
            obs_id = self._create_obs(obs_repo, rule_id, ctx_id, f"h{i}")
            ev = EvidenceRecord(
                observation_id=obs_id,
                rule_id=rule_id,
                evidence_type=EvidenceType.SUPPORTING,
                request_id=ctx_id,
                confidence_before=0.5 + 0.1 * i,
                confidence_after=0.5 + 0.1 * (i + 1),
                delta=0.1,
            )
            ev_repo.save(ev)

        history = ev_repo.get_confidence_history(rule_id)
        assert len(history) == 3

    def test_get_by_request_id(self, repositories) -> None:
        ev_repo = repositories["evidence_repository"]
        obs_repo = repositories["observation_repository"]
        rule_repo = repositories["rule_repository"]
        ctx_repo = repositories["request_context_repository"]

        rule_id = self._create_rule(rule_repo, "rule-r1")
        ctx_id = self._create_ctx(ctx_repo)

        obs_id_1 = self._create_obs(obs_repo, rule_id, ctx_id, "r1")
        obs_id_2 = self._create_obs(obs_repo, rule_id, ctx_id, "r2")

        ev1 = EvidenceRecord(
            observation_id=obs_id_1,
            rule_id=rule_id,
            evidence_type=EvidenceType.SUPPORTING,
            request_id=ctx_id,
        )
        ev2 = EvidenceRecord(
            observation_id=obs_id_2,
            rule_id=rule_id,
            evidence_type=EvidenceType.CONTRADICTING,
            request_id=ctx_id,
        )
        ev_repo.save(ev1)
        ev_repo.save(ev2)

        records = ev_repo.get_by_request_id(ctx_id)
        assert len(records) == 2


class TestRequestContextRepository:
    def test_save_and_get(self, repositories) -> None:
        ctx_repo = repositories["request_context_repository"]
        ctx = RequestContext(prompt="test query", trace_id="trace-123")
        ctx_repo.save(ctx)

        fetched = ctx_repo.get_by_id(ctx.id)
        assert fetched is not None
        assert fetched.prompt == "test query"
        assert fetched.trace_id == "trace-123"

    def test_get_all(self, repositories) -> None:
        ctx_repo = repositories["request_context_repository"]
        for i in range(3):
            ctx_repo.save(RequestContext(prompt=f"query {i}"))

        all_ctx = ctx_repo.get_all(limit=10)
        assert len(all_ctx) >= 3
