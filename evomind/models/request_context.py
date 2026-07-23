from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class RequestContext:
    id: str = field(default_factory=lambda: str(uuid4()))
    prompt: str = ""
    sql_generated: str | None = None
    guidance_injected: str | None = None
    rule_retrieved_id: str | None = None
    rule_retrieved: bool = False
    classification: str | None = None
    trace_id: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "sql_generated": self.sql_generated,
            "guidance_injected": self.guidance_injected,
            "rule_retrieved_id": self.rule_retrieved_id,
            "rule_retrieved": 1 if self.rule_retrieved else 0,
            "classification": self.classification,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RequestContext:
        return cls(
            id=data["id"],
            prompt=data["prompt"],
            sql_generated=data.get("sql_generated"),
            guidance_injected=data.get("guidance_injected"),
            rule_retrieved_id=data.get("rule_retrieved_id"),
            rule_retrieved=bool(data.get("rule_retrieved", 0)),
            classification=data.get("classification"),
            trace_id=data.get("trace_id"),
            created_at=data["created_at"],
        )
