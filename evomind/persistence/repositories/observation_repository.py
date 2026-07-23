from __future__ import annotations

from evomind.models.observation import Observation
from evomind.persistence.database import Database


class ObservationRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def get_by_id(self, observation_id: str) -> Observation | None:
        row = self._db.fetch_one(
            "SELECT * FROM observations WHERE id = ?", (observation_id,)
        )
        if row is None:
            return None
        return Observation.from_dict(dict(row))

    def get_by_request_id(self, request_id: str) -> list[Observation]:
        rows = self._db.fetch_all(
            "SELECT * FROM observations WHERE request_id = ? ORDER BY created_at",
            (request_id,),
        )
        return [Observation.from_dict(dict(r)) for r in rows]

    def get_by_rule_id(self, rule_id: str) -> list[Observation]:
        rows = self._db.fetch_all(
            "SELECT * FROM observations WHERE rule_id = ? ORDER BY created_at",
            (rule_id,),
        )
        return [Observation.from_dict(dict(r)) for r in rows]

    def save(self, observation: Observation) -> None:
        data = observation.to_dict()
        if data.get("metadata") is not None:
            import json
            data["metadata"] = json.dumps(data["metadata"])
        self._db.execute(
            """
            INSERT INTO observations (
                id, request_id, rule_id, classification, evidence_type,
                sql_generated, evaluation_reason, metadata, created_at
            ) VALUES (
                :id, :request_id, :rule_id, :classification, :evidence_type,
                :sql_generated, :evaluation_reason, :metadata, :created_at
            )
            """,
            data,
        )

    def count_by_rule_id(self, rule_id: str) -> dict[str, int]:
        rows = self._db.fetch_all(
            "SELECT evidence_type, COUNT(*) as cnt FROM observations "
            "WHERE rule_id = ? GROUP BY evidence_type",
            (rule_id,),
        )
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["evidence_type"]] = r["cnt"]
        return counts
