from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from evomind.models.enums import Classification, EvidenceType


@dataclass
class Observation:
    id: str = field(default_factory=lambda: str(uuid4()))
    request_id: str = ""
    rule_id: str = ""
    classification: Classification = Classification.AMBIGUOUS
    evidence_type: EvidenceType = EvidenceType.NEUTRAL
    sql_generated: str | None = None
    evaluation_reason: str | None = None
    metadata: dict | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "rule_id": self.rule_id,
            "classification": self.classification.value,
            "evidence_type": self.evidence_type.value,
            "sql_generated": self.sql_generated,
            "evaluation_reason": self.evaluation_reason,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Observation:
        return cls(
            id=data["id"],
            request_id=data["request_id"],
            rule_id=data["rule_id"],
            classification=Classification(data["classification"]),
            evidence_type=EvidenceType(data["evidence_type"]),
            sql_generated=data.get("sql_generated"),
            evaluation_reason=data.get("evaluation_reason"),
            metadata=data.get("metadata"),
            created_at=data["created_at"],
        )
