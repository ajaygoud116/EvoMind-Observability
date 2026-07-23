from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from evomind.config.settings import Settings


class Seed:
    DEFAULT_RULE_NAME = "use_parameterized_sql"
    DEFAULT_GUIDANCE_TEXT = (
        "IMPORTANT GUIDELINES:\n"
        "\u2022 Always use parameterized queries with ? placeholders "
        "for all user-supplied values.\n"
        "\u2022 Never use string interpolation, f-strings, or % formatting "
        "to embed values in SQL.\n"
        "\u2022 Use parameterized query syntax: WHERE id = ? "
        "(not WHERE id = {value})."
    )

    @classmethod
    def seed_default_rule(
        cls, conn: sqlite3.Connection, settings: Settings
    ) -> str | None:
        existing = conn.execute(
            "SELECT id FROM behavioral_rules WHERE name = ?",
            (cls.DEFAULT_RULE_NAME,),
        ).fetchone()

        if existing is not None:
            return existing["id"]

        import uuid

        rule_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            INSERT INTO behavioral_rules (
                id, name, description, guidance_text, condition,
                status, confidence, alpha, beta,
                promotion_threshold, demotion_threshold, min_evidence,
                supporting_count, contradicting_count,
                created_at, updated_at, promoted_at, demoted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                cls.DEFAULT_RULE_NAME,
                "Always use parameterized SQL queries instead of string interpolation.",
                cls.DEFAULT_GUIDANCE_TEXT,
                None,
                "candidate",
                0.5,
                settings.rule_initial_alpha,
                settings.rule_initial_beta,
                settings.rule_promotion_threshold,
                settings.rule_demotion_threshold,
                settings.rule_min_evidence,
                0,
                0,
                now,
                now,
                None,
                None,
            ),
        )
        return rule_id
