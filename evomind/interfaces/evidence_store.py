from __future__ import annotations

from abc import ABC, abstractmethod

from evomind.models.evidence_record import EvidenceRecord
from evomind.models.observation import Observation


class EvidenceStore(ABC):
    """Persists observations as evidence and provides evidence summaries.

    Evidence records link observations to behavioral rules and track
    the confidence before/after each update for time-series analysis.
    """

    @abstractmethod
    def append(
        self,
        observation: Observation,
        confidence_before: float,
        confidence_after: float,
    ) -> EvidenceRecord:
        """Persist an observation as evidence against a rule.

        Args:
            observation: The observation to persist.
            confidence_before: Rule confidence before this evidence.
            confidence_after: Rule confidence after this evidence.

        Returns:
            The created EvidenceRecord.

        Raises:
            EvidenceStoreError: If persistence fails.
        """

    @abstractmethod
    def get_summary(self, rule_id: str) -> dict[str, int | None]:
        """Get evidence summary for a rule.

        Returns counts per evidence type: supporting, contradicting, baseline, neutral.

        Args:
            rule_id: Rule to summarize.

        Returns:
            Dict with evidence type counts.
        """

    @abstractmethod
    def get_confidence_history(self, rule_id: str) -> list[EvidenceRecord]:
        """Get ordered confidence history for a rule.

        Args:
            rule_id: Rule to query.

        Returns:
            Chronologically ordered list of evidence records.
        """
