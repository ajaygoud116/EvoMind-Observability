from __future__ import annotations

from evomind.models.behavioral_rule import BehavioralRule
from evomind.models.enums import RuleStatus
from evomind.persistence.database import Database
from evomind.exceptions.errors import RegistryError


class RuleRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def get_by_id(self, rule_id: str) -> BehavioralRule | None:
        row = self._db.fetch_one(
            "SELECT * FROM behavioral_rules WHERE id = ?", (rule_id,)
        )
        if row is None:
            return None
        return BehavioralRule.from_dict(dict(row))

    def get_by_name(self, name: str) -> BehavioralRule | None:
        row = self._db.fetch_one(
            "SELECT * FROM behavioral_rules WHERE name = ?", (name,)
        )
        if row is None:
            return None
        return BehavioralRule.from_dict(dict(row))

    def get_active_rules(self) -> list[BehavioralRule]:
        rows = self._db.fetch_all(
            "SELECT * FROM behavioral_rules WHERE status = ?",
            (RuleStatus.ACTIVE.value,),
        )
        return [BehavioralRule.from_dict(dict(r)) for r in rows]

    def get_all(self) -> list[BehavioralRule]:
        rows = self._db.fetch_all("SELECT * FROM behavioral_rules ORDER BY created_at")
        return [BehavioralRule.from_dict(dict(r)) for r in rows]

    def save(self, rule: BehavioralRule) -> None:
        data = rule.to_dict()
        self._db.execute(
            """
            INSERT INTO behavioral_rules (
                id, name, description, guidance_text, condition,
                status, confidence, alpha, beta,
                promotion_threshold, demotion_threshold, min_evidence,
                supporting_count, contradicting_count,
                created_at, updated_at, promoted_at, demoted_at
            ) VALUES (
                :id, :name, :description, :guidance_text, :condition,
                :status, :confidence, :alpha, :beta,
                :promotion_threshold, :demotion_threshold, :min_evidence,
                :supporting_count, :contradicting_count,
                :created_at, :updated_at, :promoted_at, :demoted_at
            )
            """,
            data,
        )

    def update(self, rule: BehavioralRule) -> None:
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rule.updated_at = now
        data = rule.to_dict()
        self._db.execute(
            """
            UPDATE behavioral_rules SET
                status = :status,
                confidence = :confidence,
                alpha = :alpha,
                beta = :beta,
                promotion_threshold = :promotion_threshold,
                demotion_threshold = :demotion_threshold,
                min_evidence = :min_evidence,
                supporting_count = :supporting_count,
                contradicting_count = :contradicting_count,
                updated_at = :updated_at,
                promoted_at = :promoted_at,
                demoted_at = :demoted_at
            WHERE id = :id
            """,
            data,
        )

    def delete(self, rule_id: str) -> None:
        self._db.execute(
            "DELETE FROM behavioral_rules WHERE id = ?", (rule_id,)
        )

    def count(self) -> int:
        row = self._db.fetch_one("SELECT COUNT(*) as cnt FROM behavioral_rules")
        return row["cnt"] if row else 0
