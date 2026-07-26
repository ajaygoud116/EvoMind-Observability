from __future__ import annotations

import os as _os
import sqlite3
import tempfile as _tempfile
import uuid as _uuid

import pytest

from evomind.config.settings import Settings
from evomind.exceptions.errors import DatabaseError
from evomind.persistence.database import Database
from evomind.persistence.schema import Schema


class TestDatabase:
    def test_commit_persists_data(self) -> None:
        db_path = _os.path.join(_tempfile.gettempdir(), f"evomind_{_uuid.uuid4().hex}.db")
        try:
            settings = Settings(database_path=db_path, otel_enabled=False)
            db = Database(settings)
            db.initialize()
            db.execute(
                "INSERT INTO behavioral_rules (id, name, guidance_text, created_at, updated_at) "
                "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                ("commit-test", "commit_rule", "test"),
            )
            db.commit()
            db.close()
            db2 = Database(settings)
            db2.initialize()
            row = db2.fetch_one("SELECT * FROM behavioral_rules WHERE id = ?", ("commit-test",))
            assert row is not None
            assert row["name"] == "commit_rule"
            db2.close()
        finally:
            if _os.path.exists(db_path):
                _os.remove(db_path)

    def test_rollback_undoes_data(self) -> None:
        db_path = _os.path.join(_tempfile.gettempdir(), f"evomind_{_uuid.uuid4().hex}.db")
        try:
            settings = Settings(database_path=db_path, otel_enabled=False)
            db = Database(settings)
            db.initialize()
            db.execute(
                "INSERT INTO behavioral_rules (id, name, guidance_text, created_at, updated_at) "
                "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                ("rb-test", "rb_rule", "test"),
            )
            db.rollback()
            row = db.fetch_one("SELECT * FROM behavioral_rules WHERE id = ?", ("rb-test",))
            assert row is None
            db.close()
        finally:
            if _os.path.exists(db_path):
                _os.remove(db_path)

    def test_initialize_and_query(self, database) -> None:
        """Database initializes without error and can run queries."""
        result = database.fetch_one("SELECT COUNT(*) as cnt FROM behavioral_rules")
        assert result is not None
        assert result["cnt"] >= 0

    def test_initialize_idempotent(self, database) -> None:
        """Calling initialize twice should not error."""
        database.initialize()
        result = database.fetch_one("SELECT COUNT(*) as cnt FROM behavioral_rules")
        assert result is not None

    def test_execute_and_fetch(self, database) -> None:
        """Basic insert and select work."""
        database.execute(
            "INSERT INTO behavioral_rules (id, name, guidance_text, created_at, updated_at) "
            "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            ("test-1", "test_rule", "test guidance"),
        )
        row = database.fetch_one(
            "SELECT * FROM behavioral_rules WHERE id = ?", ("test-1",)
        )
        assert row is not None
        assert row["name"] == "test_rule"

    def test_fetch_all(self, database) -> None:
        """Fetch all returns multiple rows."""
        database.execute(
            "INSERT INTO behavioral_rules (id, name, guidance_text, created_at, updated_at) "
            "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            ("a1", "rule_a", "g1"),
        )
        database.execute(
            "INSERT INTO behavioral_rules (id, name, guidance_text, created_at, updated_at) "
            "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            ("a2", "rule_b", "g2"),
        )
        rows = database.fetch_all(
            "SELECT * FROM behavioral_rules WHERE id IN (?, ?)", ("a1", "a2")
        )
        assert len(rows) == 2

    def test_reset(self, database) -> None:
        """Reset drops and recreates tables."""
        database.execute(
            "INSERT INTO behavioral_rules (id, name, guidance_text, created_at, updated_at) "
            "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            ("r1", "temp_rule", "g"),
        )
        database.reset()
        count = database.fetch_one(
            "SELECT COUNT(*) as cnt FROM behavioral_rules"
        )
        # Seeded default rule exists after reset
        assert count["cnt"] == 1

    def test_connection_thread_safety(self, database) -> None:
        """Connection property returns a working connection."""
        conn = database.connection
        assert conn is not None
        result = conn.execute("SELECT 1 as val").fetchone()
        assert result["val"] == 1

    def test_close(self, database) -> None:
        """Close should not error."""
        database.close()

    def test_create_all_schema(self, database) -> None:
        """All tables exist after initialization."""
        tables = database.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [t["name"] for t in tables]
        assert "behavioral_rules" in table_names
        assert "observations" in table_names
        assert "evidence_records" in table_names
        assert "request_contexts" in table_names

    def test_indexes_exist(self, database) -> None:
        """Required indexes exist."""
        indexes = database.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        index_names = [i["name"] for i in indexes]
        assert "idx_observations_rule_id" in index_names
        assert "idx_evidence_records_rule_id" in index_names
        assert "idx_evidence_records_created_at" in index_names
        assert "idx_request_contexts_created_at" in index_names
