from __future__ import annotations

from datetime import datetime, timezone

from evomind.exceptions.errors import ConfidenceError
from evomind.interfaces.confidence_engine import ConfidenceEngine as ConfidenceEngineABC
from evomind.models.enums import EvidenceType, RuleStatus
from evomind.persistence.repositories.rule_repository import RuleRepository


class ConfidenceEngine(ConfidenceEngineABC):
    """Beta-Bernoulli confidence engine.

    - Supporting evidence: α += 1
    - Contradicting evidence: β += 1
    - Baseline/Neutral: no update
    - Confidence = α / (α + β)

    After each update, checks and executes rule state transitions:
    - Candidate → Active: confidence >= promotion_threshold AND total_evidence >= min_evidence
    - Active → Suspended: confidence < demotion_threshold
    - Suspended → Active: confidence >= promotion_threshold
    """

    def __init__(self, rule_repository: RuleRepository) -> None:
        self._rule_repo = rule_repository

    def update(
        self,
        rule_id: str,
        evidence_type: EvidenceType,
    ) -> dict:
        rule = self._rule_repo.get_by_id(rule_id)
        if rule is None:
            raise ConfidenceError(f"Rule not found: {rule_id}")

        alpha = rule.alpha
        beta = rule.beta
        supporting_count = rule.supporting_count
        contradicting_count = rule.contradicting_count

        if evidence_type == EvidenceType.SUPPORTING:
            alpha += 1.0
            supporting_count += 1
        elif evidence_type == EvidenceType.CONTRADICTING:
            beta += 1.0
            contradicting_count += 1

        confidence_before = rule.confidence
        confidence_after = alpha / (alpha + beta)

        rule.alpha = alpha
        rule.beta = beta
        rule.confidence = confidence_after
        rule.supporting_count = supporting_count
        rule.contradicting_count = contradicting_count
        rule.updated_at = datetime.now(timezone.utc).isoformat()

        from_status = rule.status.value
        transitioned = False
        to_status: str | None = None
        reason: str | None = None

        if rule.should_promote:
            rule.status = RuleStatus.ACTIVE
            rule.promoted_at = datetime.now(timezone.utc).isoformat()
            transitioned = True
            to_status = RuleStatus.ACTIVE.value
            reason = (
                f"Confidence {confidence_after:.4f} >= {rule.promotion_threshold} "
                f"with {rule.total_evidence} evidence (min {rule.min_evidence})"
            )
        elif rule.should_demote:
            rule.status = RuleStatus.SUSPENDED
            rule.demoted_at = datetime.now(timezone.utc).isoformat()
            transitioned = True
            to_status = RuleStatus.SUSPENDED.value
            reason = f"Confidence {confidence_after:.4f} < {rule.demotion_threshold}"
        elif rule.should_re_promote:
            rule.status = RuleStatus.ACTIVE
            rule.promoted_at = datetime.now(timezone.utc).isoformat()
            transitioned = True
            to_status = RuleStatus.ACTIVE.value
            reason = (
                f"Re-promoted: Confidence {confidence_after:.4f} >= "
                f"{rule.promotion_threshold}"
            )
        elif (
            rule.status == RuleStatus.SUSPENDED
            and evidence_type == EvidenceType.CONTRADICTING
            and rule.contradicting_count > rule.supporting_count
        ):
            rule.status = RuleStatus.ARCHIVED
            rule.archived_at = datetime.now(timezone.utc).isoformat()
            transitioned = True
            to_status = RuleStatus.ARCHIVED.value
            reason = (
                f"Archived: contradicting ({rule.contradicting_count}) > "
                f"supporting ({rule.supporting_count})"
            )

        self._rule_repo.update(rule)

        return {
            "rule_id": rule_id,
            "confidence_before": confidence_before,
            "confidence_after": confidence_after,
            "delta": confidence_after - confidence_before,
            "alpha": alpha,
            "beta": beta,
            "evidence_type": evidence_type.value,
            "status_changed": transitioned,
            "from_status": from_status if transitioned else None,
            "to_status": to_status,
            "reason": reason,
        }
