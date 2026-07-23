from __future__ import annotations

import uuid

import pytest

from evomind.config.settings import Settings
from evomind.learning.rule_retriever import RuleRetriever
from evomind.models.behavioral_rule import BehavioralRule
from evomind.models.enums import RuleStatus
from evomind.models.request_context import RequestContext
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
def retriever(rule_repo: RuleRepository) -> RuleRetriever:
    return RuleRetriever(rule_repo)


class TestRuleRetriever:
    def test_returns_empty_when_no_active_rules(
        self, retriever: RuleRetriever, seeded_rule_id: str
    ) -> None:
        ctx = RequestContext(prompt="show users")
        rules = retriever.retrieve(ctx)
        assert rules == []

    def test_returns_active_rule_when_promoted(
        self, retriever: RuleRetriever, rule_repo: RuleRepository, seeded_rule_id: str
    ) -> None:
        rule = rule_repo.get_by_id(seeded_rule_id)
        rule.status = RuleStatus.ACTIVE
        rule_repo.update(rule)

        ctx = RequestContext(prompt="show users")
        rules = retriever.retrieve(ctx)
        assert len(rules) == 1
        assert rules[0].id == seeded_rule_id
        assert rules[0].status == RuleStatus.ACTIVE

    def test_does_not_return_candidate_rules(
        self, retriever: RuleRetriever, seeded_rule_id: str
    ) -> None:
        ctx = RequestContext(prompt="show users")
        rules = retriever.retrieve(ctx)
        for r in rules:
            assert r.status != RuleStatus.CANDIDATE

    def test_does_not_return_suspended_rules(
        self, retriever: RuleRetriever, rule_repo: RuleRepository, seeded_rule_id: str
    ) -> None:
        rule = rule_repo.get_by_id(seeded_rule_id)
        rule.status = RuleStatus.SUSPENDED
        rule_repo.update(rule)

        ctx = RequestContext(prompt="show users")
        rules = retriever.retrieve(ctx)
        assert rules == []

    def test_does_not_return_archived_rules(
        self, retriever: RuleRetriever, rule_repo: RuleRepository, seeded_rule_id: str
    ) -> None:
        rule = rule_repo.get_by_id(seeded_rule_id)
        rule.status = RuleStatus.ARCHIVED
        rule_repo.update(rule)

        ctx = RequestContext(prompt="show users")
        rules = retriever.retrieve(ctx)
        assert rules == []

    def test_returns_all_active_rules(
        self, retriever: RuleRetriever, rule_repo: RuleRepository
    ) -> None:
        r1 = BehavioralRule(
            name="rule-1", status=RuleStatus.ACTIVE, guidance_text="use ?"
        )
        r2 = BehavioralRule(
            name="rule-2", status=RuleStatus.ACTIVE, guidance_text="avoid *"
        )
        rule_repo.save(r1)
        rule_repo.save(r2)

        ctx = RequestContext(prompt="show users")
        rules = retriever.retrieve(ctx)
        assert len(rules) == 2

    def test_context_not_modified(self, retriever: RuleRetriever) -> None:
        ctx = RequestContext(prompt="original prompt")
        prompt_before = ctx.prompt
        retriever.retrieve(ctx)
        assert ctx.prompt == prompt_before
