from __future__ import annotations

import pytest

from evomind.learning.guidance_injector import GuidanceInjector
from evomind.models.behavioral_rule import BehavioralRule
from evomind.models.enums import RuleStatus


@pytest.fixture
def injector() -> GuidanceInjector:
    return GuidanceInjector()


@pytest.fixture
def active_rule() -> BehavioralRule:
    return BehavioralRule(
        name="use_parameterized_sql",
        status=RuleStatus.ACTIVE,
        guidance_text="Always use parameterized queries with ? placeholders.",
    )


class TestGuidanceInjector:
    def test_inject_prepends_guidance(
        self, injector: GuidanceInjector, active_rule: BehavioralRule
    ) -> None:
        result = injector.inject("show me users", [active_rule])
        assert "=== BEHAVIORAL GUIDELINES ===" in result
        assert "Always use parameterized queries" in result
        assert "=== END GUIDELINES ===" in result
        assert "show me users" in result

    def test_inject_does_not_change_prompt(
        self, injector: GuidanceInjector, active_rule: BehavioralRule
    ) -> None:
        original = "show me users"
        result = injector.inject(original, [active_rule])
        assert original in result

    def test_inject_guidance_appears_before_prompt(
        self, injector: GuidanceInjector, active_rule: BehavioralRule
    ) -> None:
        result = injector.inject("show me users", [active_rule])
        guidelines_idx = result.index("=== BEHAVIORAL GUIDELINES ===")
        prompt_idx = result.index("show me users")
        assert guidelines_idx < prompt_idx

    def test_inject_multiple_rules(
        self, injector: GuidanceInjector
    ) -> None:
        r1 = BehavioralRule(
            name="rule-1",
            status=RuleStatus.ACTIVE,
            guidance_text="Use parameterized queries.",
        )
        r2 = BehavioralRule(
            name="rule-2",
            status=RuleStatus.ACTIVE,
            guidance_text="Avoid SELECT *.",
        )
        result = injector.inject("show me users", [r1, r2])
        assert "Use parameterized queries." in result
        assert "Avoid SELECT *." in result

    def test_inject_empty_rule_list_returns_prompt(
        self, injector: GuidanceInjector
    ) -> None:
        result = injector.inject("show me users", [])
        assert result == "show me users"

    def test_inject_prompt_length_recorded(
        self, injector: GuidanceInjector, active_rule: BehavioralRule
    ) -> None:
        original = "show me users"
        result = injector.inject(original, [active_rule])
        assert len(result) > len(original)

    def test_inject_empty_prompt_raises(
        self, injector: GuidanceInjector, active_rule: BehavioralRule
    ) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            injector.inject("", [active_rule])

    def test_inject_whitespace_prompt_raises(
        self, injector: GuidanceInjector, active_rule: BehavioralRule
    ) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            injector.inject("   ", [active_rule])

    def test_inject_format_consistent(
        self, injector: GuidanceInjector, active_rule: BehavioralRule
    ) -> None:
        result1 = injector.inject("prompt a", [active_rule])
        result2 = injector.inject("prompt b", [active_rule])
        assert result1.startswith("=== BEHAVIORAL GUIDELINES ===")
        assert result2.startswith("=== BEHAVIORAL GUIDELINES ===")
