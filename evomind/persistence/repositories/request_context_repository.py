from __future__ import annotations

from evomind.models.request_context import RequestContext
from evomind.persistence.database import Database


class RequestContextRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def get_by_id(self, request_id: str) -> RequestContext | None:
        row = self._db.fetch_one(
            "SELECT * FROM request_contexts WHERE id = ?", (request_id,)
        )
        if row is None:
            return None
        return RequestContext.from_dict(dict(row))

    def save(self, context: RequestContext) -> None:
        self._db.execute(
            """
            INSERT INTO request_contexts (
                id, prompt, sql_generated, guidance_injected,
                rule_retrieved_id, rule_retrieved, classification,
                trace_id, created_at
            ) VALUES (
                :id, :prompt, :sql_generated, :guidance_injected,
                :rule_retrieved_id, :rule_retrieved, :classification,
                :trace_id, :created_at
            )
            """,
            context.to_dict(),
        )

    def get_all(self, limit: int = 100) -> list[RequestContext]:
        rows = self._db.fetch_all(
            "SELECT * FROM request_contexts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [RequestContext.from_dict(dict(r)) for r in rows]
