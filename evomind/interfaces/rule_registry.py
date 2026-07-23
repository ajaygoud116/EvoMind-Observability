from __future__ import annotations

from abc import ABC, abstractmethod

from evomind.models.behavioral_rule import BehavioralRule


class RuleRegistry(ABC):
    """Manages behavioral rule persistence and lifecycle.

    Enforces state transitions. No component other than the registry
    may change a rule's status directly.
    """

    @abstractmethod
    def get_rule(self, rule_id: str) -> BehavioralRule | None:
        """Get a rule by ID."""

    @abstractmethod
    def get_rule_by_name(self, name: str) -> BehavioralRule | None:
        """Get a rule by name."""

    @abstractmethod
    def get_active_rules(self) -> list[BehavioralRule]:
        """Get all rules with status = active."""

    @abstractmethod
    def save(self, rule: BehavioralRule) -> None:
        """Persist a new rule."""

    @abstractmethod
    def update_confidence(
        self,
        rule_id: str,
        alpha: float,
        beta: float,
        confidence: float,
    ) -> BehavioralRule:
        """Update a rule's Bayesian parameters after confidence computation."""

    @abstractmethod
    def check_transition(self, rule_id: str) -> dict:
        """Check and execute state transitions.

        Returns dict with: transitioned (bool), from_status (str|None),
        to_status (str|None), reason (str|None).
        """

    @abstractmethod
    def get_all(self) -> list[BehavioralRule]:
        """Get all rules."""
