from __future__ import annotations

from abc import ABC, abstractmethod

from evomind.models.evaluation_result import EvaluationResult


class OutcomeEvaluator(ABC):
    """Evaluates generated SQL for safety.

    Deterministic, rule-based classification. Never executes SQL.
    """

    @abstractmethod
    def evaluate(self, sql: str) -> EvaluationResult:
        """Classify a SQL string as safe, unsafe, or ambiguous.

        Args:
            sql: The SQL string to evaluate.

        Returns:
            EvaluationResult with classification, reason, and detected patterns.

        Raises:
            EvaluationError: If SQL parsing fails.
            ValueError: If sql is empty or None.
        """
