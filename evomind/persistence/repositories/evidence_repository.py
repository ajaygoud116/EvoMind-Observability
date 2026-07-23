from __future__ import annotations

from evomind.models.evidence_record import EvidenceRecord
from evomind.persistence.database import Database


class EvidenceRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def get_by_id(self, evidence_id: str) -> EvidenceRecord | None:
        row = self._db.fetch_one(
            "SELECT * FROM evidence_records WHERE id = ?", (evidence_id,)
        )
        if row is None:
            return None
        return EvidenceRecord.from_dict(dict(row))

    def get_by_rule_id(self, rule_id: str) -> list[EvidenceRecord]:
        rows = self._db.fetch_all(
            "SELECT * FROM evidence_records WHERE rule_id = ? ORDER BY created_at",
            (rule_id,),
        )
        return [EvidenceRecord.from_dict(dict(r)) for r in rows]

    def get_by_request_id(self, request_id: str) -> list[EvidenceRecord]:
        rows = self._db.fetch_all(
            "SELECT * FROM evidence_records WHERE request_id = ? ORDER BY created_at",
            (request_id,),
        )
        return [EvidenceRecord.from_dict(dict(r)) for r in rows]

    def save(self, record: EvidenceRecord) -> None:
        self._db.execute(
            """
            INSERT INTO evidence_records (
                id, observation_id, rule_id, evidence_type, request_id,
                confidence_before, confidence_after, delta, created_at
            ) VALUES (
                :id, :observation_id, :rule_id, :evidence_type, :request_id,
                :confidence_before, :confidence_after, :delta, :created_at
            )
            """,
            record.to_dict(),
        )

    def get_summary(self, rule_id: str) -> dict[str, int | None]:
        rows = self._db.fetch_all(
            "SELECT evidence_type, COUNT(*) as cnt FROM evidence_records "
            "WHERE rule_id = ? GROUP BY evidence_type",
            (rule_id,),
        )
        summary: dict[str, int | None] = {
            "supporting": None,
            "contradicting": None,
            "baseline": None,
            "neutral": None,
        }
        for r in rows:
            summary[r["evidence_type"]] = r["cnt"]
        return summary

    def get_confidence_history(self, rule_id: str) -> list[EvidenceRecord]:
        rows = self._db.fetch_all(
            "SELECT * FROM evidence_records WHERE rule_id = ? "
            "ORDER BY created_at ASC",
            (rule_id,),
        )
        return [EvidenceRecord.from_dict(dict(r)) for r in rows]
