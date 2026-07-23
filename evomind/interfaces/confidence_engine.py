from __future__ import annotations

from abc import ABC, abstractmethod

from evomind.models.enums import EvidenceType


class ConfidenceEngine(ABC):
    """Computes and updates confidence scores for behavioral rules.

    Uses a Beta-Bernoulli conjugate model:
    - Supporting evidence: α += 1
    - Contradicting evidence: β += 1
    - Baseline/Neutral evidence: no update
    - Confidence = α / (α + β)
    """

    @abstractmethod
    def update(
        self,
        rule_id: str,
        evidence_type: EvidenceType,
    ) -> dict:
        """Update a rule's confidence based on new evidence.

        Args:
            rule_id: The rule to update.
            evidence_type: Type of evidence (supporting/contradicting/baseline/neutral).

        Returns:
            Dict with keys: rule_id, confidence_before, confidence_after, delta,
            alpha, beta, evidence_type, status_changed, from_status, to_status.

        Raises:
            ConfidenceError: If computation fails.
            KeyError: If rule_id is not found.
        """
