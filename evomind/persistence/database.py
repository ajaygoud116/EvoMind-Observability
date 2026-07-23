from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from evomind.config.settings import Settings
from evomind.exceptions.errors import DatabaseError
from evomind.persistence.schema import Schema
from evomind.persistence.seed import Seed


class Database:
    """Manages the SQLite connection lifecycle.

    Uses a thread-local connection to support concurrent access
    within a single-process async application.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._local = threading.local()
        self._lock = threading.Lock()

    @property
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = self._create_connection()
            self._local.connection = conn
        return conn

    def _create_connection(self) -> sqlite3.Connection:
        db_path = self._settings.database_path
        if db_path == ":memory:":
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True, check_same_thread=False)
        elif db_path.startswith("file:"):
            conn = sqlite3.connect(db_path, uri=True, check_same_thread=False)
        else:
            conn = sqlite3.connect(str(Path(db_path)), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create schema and seed initial data."""
        try:
            Schema.create_all(self.connection)
            Seed.seed_default_rule(self.connection, self._settings)
            self.connection.commit()
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise DatabaseError(f"Database initialization failed: {exc}") from exc

    def reset(self) -> None:
        """Drop all tables and re-initialize. For testing only."""
        try:
            Schema.drop_all(self.connection)
            self.connection.commit()
            self.initialize()
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise DatabaseError(f"Database reset failed: {exc}") from exc

    def close(self) -> None:
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            conn.close()
            self._local.connection = None

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        try:
            return self.connection.execute(sql, params)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Query failed: {exc}") from exc

    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        try:
            self.connection.executemany(sql, params_list)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Batch query failed: {exc}") from exc

    def fetch_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def fetch_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()

    @property
    def last_insert_rowid(self) -> int:
        return self.execute("SELECT last_insert_rowid()").fetchone()[0]
