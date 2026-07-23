from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from evomind.models.enums import RuleStatus


@dataclass
class BehavioralRule:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str | None = None
    guidance_text: str = ""
    condition: str | None = None
    status: RuleStatus = RuleStatus.CANDIDATE
    confidence: float = 0.5
    alpha: float = 1.0
    beta: float = 1.0
    promotion_threshold: float = 0.75
    demotion_threshold: float = 0.35
    min_evidence: int = 3
    supporting_count: int = 0
    contradicting_count: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    promoted_at: str | None = None
    demoted_at: str | None = None

    @property
    def total_evidence(self) -> int:
        return self.supporting_count + self.contradicting_count

    @property
    def should_promote(self) -> bool:
        return (
            self.status == RuleStatus.CANDIDATE
            and self.confidence >= self.promotion_threshold
            and self.total_evidence >= self.min_evidence
        )

    @property
    def should_demote(self) -> bool:
        return (
            self.status == RuleStatus.ACTIVE
            and self.confidence < self.demotion_threshold
        )

    @property
    def should_re_promote(self) -> bool:
        return (
            self.status == RuleStatus.SUSPENDED
            and self.confidence >= self.promotion_threshold
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "guidance_text": self.guidance_text,
            "condition": self.condition,
            "status": self.status.value,
            "confidence": self.confidence,
            "alpha": self.alpha,
            "beta": self.beta,
            "promotion_threshold": self.promotion_threshold,
            "demotion_threshold": self.demotion_threshold,
            "min_evidence": self.min_evidence,
            "supporting_count": self.supporting_count,
            "contradicting_count": self.contradicting_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "promoted_at": self.promoted_at,
            "demoted_at": self.demoted_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BehavioralRule:
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            guidance_text=data["guidance_text"],
            condition=data.get("condition"),
            status=RuleStatus(data["status"]),
            confidence=data["confidence"],
            alpha=data["alpha"],
            beta=data["beta"],
            promotion_threshold=data["promotion_threshold"],
            demotion_threshold=data["demotion_threshold"],
            min_evidence=data["min_evidence"],
            supporting_count=data["supporting_count"],
            contradicting_count=data["contradicting_count"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            promoted_at=data.get("promoted_at"),
            demoted_at=data.get("demoted_at"),
        )
