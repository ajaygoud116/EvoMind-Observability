from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class LearningState:
    id: str = field(default_factory=lambda: str(uuid4()))
    request_id: str = ""
    rule_id: str = ""
    confidence: float = 0.0
    status: str = ""
    supporting_count: int = 0
    contradicting_count: int = 0
    total_evidence: int = 0
    snapshot_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
