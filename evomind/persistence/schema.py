from __future__ import annotations

import sqlite3


class Schema:
    DDL: str = """
    CREATE TABLE IF NOT EXISTS behavioral_rules (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        guidance_text TEXT NOT NULL,
        condition TEXT,
        status TEXT NOT NULL DEFAULT 'candidate'
            CHECK (status IN ('candidate', 'active', 'suspended', 'archived')),
        confidence REAL NOT NULL DEFAULT 0.5
            CHECK (confidence >= 0.0 AND confidence <= 1.0),
        alpha REAL NOT NULL DEFAULT 1.0 CHECK (alpha > 0.0),
        beta REAL NOT NULL DEFAULT 1.0 CHECK (beta > 0.0),
        promotion_threshold REAL NOT NULL DEFAULT 0.75,
        demotion_threshold REAL NOT NULL DEFAULT 0.35,
        min_evidence INTEGER NOT NULL DEFAULT 3,
        supporting_count INTEGER NOT NULL DEFAULT 0,
        contradicting_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        promoted_at TEXT,
        demoted_at TEXT
    );

    CREATE TABLE IF NOT EXISTS observations (
        id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL REFERENCES request_contexts(id),
        rule_id TEXT NOT NULL REFERENCES behavioral_rules(id),
        classification TEXT NOT NULL
            CHECK (classification IN ('safe', 'unsafe', 'ambiguous')),
        evidence_type TEXT NOT NULL
            CHECK (evidence_type IN ('supporting', 'contradicting', 'baseline', 'neutral')),
        sql_generated TEXT,
        evaluation_reason TEXT,
        metadata TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS evidence_records (
        id TEXT PRIMARY KEY,
        observation_id TEXT NOT NULL REFERENCES observations(id),
        rule_id TEXT NOT NULL REFERENCES behavioral_rules(id),
        evidence_type TEXT NOT NULL
            CHECK (evidence_type IN ('supporting', 'contradicting', 'baseline', 'neutral')),
        request_id TEXT NOT NULL REFERENCES request_contexts(id),
        confidence_before REAL NOT NULL,
        confidence_after REAL NOT NULL,
        delta REAL NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS request_contexts (
        id TEXT PRIMARY KEY,
        prompt TEXT NOT NULL,
        sql_generated TEXT,
        guidance_injected TEXT,
        rule_retrieved_id TEXT REFERENCES behavioral_rules(id),
        rule_retrieved BOOLEAN NOT NULL DEFAULT 0,
        classification TEXT,
        trace_id TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS learning_states (
        id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL REFERENCES request_contexts(id),
        rule_id TEXT NOT NULL REFERENCES behavioral_rules(id),
        confidence REAL NOT NULL,
        status TEXT NOT NULL,
        supporting_count INTEGER NOT NULL,
        contradicting_count INTEGER NOT NULL,
        total_evidence INTEGER NOT NULL,
        snapshot_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_observations_rule_id ON observations(rule_id);
    CREATE INDEX IF NOT EXISTS idx_observations_request_id ON observations(request_id);
    CREATE INDEX IF NOT EXISTS idx_evidence_records_rule_id ON evidence_records(rule_id);
    CREATE INDEX IF NOT EXISTS idx_evidence_records_created_at ON evidence_records(created_at);
    CREATE INDEX IF NOT EXISTS idx_request_contexts_created_at ON request_contexts(created_at);
    CREATE INDEX IF NOT EXISTS idx_learning_states_rule_id ON learning_states(rule_id);
    """

    DROP_ALL: str = """
    DROP TABLE IF EXISTS learning_states;
    DROP TABLE IF EXISTS evidence_records;
    DROP TABLE IF EXISTS observations;
    DROP TABLE IF EXISTS request_contexts;
    DROP TABLE IF EXISTS behavioral_rules;
    """

    @classmethod
    def create_all(cls, conn: sqlite3.Connection) -> None:
        conn.executescript(cls.DDL)

    @classmethod
    def drop_all(cls, conn: sqlite3.Connection) -> None:
        conn.executescript(cls.DROP_ALL)
