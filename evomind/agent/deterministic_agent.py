from __future__ import annotations

import hashlib

from evomind.exceptions.errors import AgentGenerationError
from evomind.interfaces.sql_agent import SQLAgent


class DeterministicSQLAgent(SQLAgent):
    """Deterministic SQL agent that maps prompts to SQL via keyword matching.

    Without guidance: produces SQL with inline values (unsafe).
    With guidance: produces parameterized SQL using ? placeholders (safe).
    """

    def generate(self, prompt: str, guidance: str | None = None) -> str:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")

        try:
            lower = prompt.strip().lower()

            if guidance is not None:
                return self._generate_safe(lower)
            return self._generate_unsafe(lower, prompt)
        except Exception as exc:
            raise AgentGenerationError(f"SQL generation failed: {exc}") from exc

    def _generate_unsafe(self, lower: str, original: str) -> str:
        if "delete" in lower or "remove" in lower:
            return "DELETE FROM users"
        if "drop" in lower:
            return "DROP TABLE users"
        if "truncate" in lower:
            return "TRUNCATE TABLE users"
        if "alter" in lower:
            return "ALTER TABLE users DROP COLUMN password"
        if "insert" in lower or "add" in lower:
            return "INSERT INTO users (name, email) VALUES ('admin', 'admin@example.com')"
        if "update" in lower or "change" in lower or "modify" in lower:
            return "UPDATE users SET email = 'hacker@evil.com' WHERE id = 1"
        if "select" in lower or "find" in lower or "get" in lower or "show" in lower:
            return self._select_unsafe(lower)
        if "order" in lower or "purchase" in lower:
            return "SELECT * FROM orders WHERE customer_id = 123"
        if "product" in lower or "item" in lower:
            return "SELECT * FROM products WHERE name = 'widget'"
        return "SELECT * FROM users WHERE username = 'admin'"

    def _select_unsafe(self, lower: str) -> str:
        if "user" in lower or "customer" in lower or "person" in lower:
            return "SELECT * FROM users WHERE username = 'admin'"
        if "order" in lower:
            return "SELECT * FROM orders WHERE total > 1000"
        if "product" in lower or "item" in lower or "inventory" in lower:
            return "SELECT * FROM products WHERE name = 'test'"
        if "password" in lower or "credential" in lower or "secret" in lower:
            return "SELECT password FROM credentials WHERE id = 1"
        if "salary" in lower or "pay" in lower or "compensation" in lower:
            return "SELECT salary FROM employees WHERE name = 'John'"
        if "email" in lower:
            return "SELECT * FROM emails WHERE recipient = 'ceo@company.com'"
        if "all" in lower or "everything" in lower or "*" in lower:
            return "SELECT * FROM users"
        if "join" in lower:
            return "SELECT * FROM users u JOIN orders o ON u.id = o.user_id WHERE u.name = 'admin'"
        return "SELECT * FROM sensitive_data"

    def _generate_safe(self, lower: str) -> str:
        if "delete" in lower or "remove" in lower:
            return "DELETE FROM users WHERE id = ?"
        if "drop" in lower:
            return "DROP TABLE IF EXISTS ?"
        if "insert" in lower or "add" in lower:
            return "INSERT INTO users (name, email) VALUES (?, ?)"
        if "update" in lower or "change" in lower or "modify" in lower:
            return "UPDATE users SET email = ? WHERE id = ?"
        if "truncate" in lower:
            return "TRUNCATE TABLE ?"
        if "select" in lower or "find" in lower or "get" in lower or "show" in lower:
            return self._select_safe(lower)
        return "SELECT * FROM users WHERE username = ?"

    def _select_safe(self, lower: str) -> str:
        if "user" in lower or "customer" in lower:
            return "SELECT * FROM users WHERE username = ?"
        if "order" in lower:
            return "SELECT * FROM orders WHERE customer_id = ?"
        if "product" in lower or "item" in lower:
            return "SELECT * FROM products WHERE name = ?"
        return "SELECT * FROM users WHERE id = ?"
