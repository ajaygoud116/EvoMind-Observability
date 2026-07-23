from __future__ import annotations

from evomind.models.learning_state import LearningState
from evomind.persistence.database import Database


class LearningStateRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def save(self, state: LearningState) -> None:
        self._db.execute(
            """
            INSERT INTO learning_states (
                id, request_id, rule_id, confidence, status,
                supporting_count, contradicting_count, total_evidence, snapshot_at
            ) VALUES (
                :id, :request_id, :rule_id, :confidence, :status,
                :supporting_count, :contradicting_count, :total_evidence, :snapshot_at
            )
            """,
            {
                "id": state.id,
                "request_id": state.request_id,
                "rule_id": state.rule_id,
                "confidence": state.confidence,
                "status": state.status,
                "supporting_count": state.supporting_count,
                "contradicting_count": state.contradicting_count,
                "total_evidence": state.total_evidence,
                "snapshot_at": state.snapshot_at,
            },
        )

    def get_by_rule_id(self, rule_id: str, limit: int = 50) -> list[LearningState]:
        rows = self._db.fetch_all(
            "SELECT * FROM learning_states WHERE rule_id = ? "
            "ORDER BY snapshot_at DESC LIMIT ?",
            (rule_id, limit),
        )
        return [self._row_to_state(r) for r in rows]

    def get_by_request_id(self, request_id: str) -> list[LearningState]:
        rows = self._db.fetch_all(
            "SELECT * FROM learning_states WHERE request_id = ? "
            "ORDER BY snapshot_at DESC",
            (request_id,),
        )
        return [self._row_to_state(r) for r in rows]

    def _row_to_state(self, row) -> LearningState:
        return LearningState(
            id=row["id"],
            request_id=row["request_id"],
            rule_id=row["rule_id"],
            confidence=row["confidence"],
            status=row["status"],
            supporting_count=row["supporting_count"],
            contradicting_count=row["contradicting_count"],
            total_evidence=row["total_evidence"],
            snapshot_at=row["snapshot_at"],
        )
