from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from evomind.models.enums import EvidenceType


@dataclass
class EvidenceRecord:
    id: str = field(default_factory=lambda: str(uuid4()))
    observation_id: str = ""
    rule_id: str = ""
    evidence_type: EvidenceType = EvidenceType.NEUTRAL
    request_id: str = ""
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    delta: float = 0.0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "observation_id": self.observation_id,
            "rule_id": self.rule_id,
            "evidence_type": self.evidence_type.value,
            "request_id": self.request_id,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "delta": self.delta,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EvidenceRecord:
        return cls(
            id=data["id"],
            observation_id=data["observation_id"],
            rule_id=data["rule_id"],
            evidence_type=EvidenceType(data["evidence_type"]),
            request_id=data["request_id"],
            confidence_before=data["confidence_before"],
            confidence_after=data["confidence_after"],
            delta=data["delta"],
            created_at=data["created_at"],
        )
