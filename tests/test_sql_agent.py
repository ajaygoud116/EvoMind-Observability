from __future__ import annotations

import pytest

from evomind.agent.deterministic_agent import DeterministicSQLAgent
from evomind.exceptions.errors import AgentGenerationError


class TestDeterministicSQLAgent:
    def setup_method(self) -> None:
        self.agent = DeterministicSQLAgent()

    def test_generate_select_users(self) -> None:
        sql = self.agent.generate("show me all users")
        assert "SELECT" in sql
        assert "users" in sql

    def test_generate_delete(self) -> None:
        sql = self.agent.generate("delete user with id 1")
        assert "DELETE" in sql
        assert "FROM" in sql

    def test_generate_drop(self) -> None:
        sql = self.agent.generate("drop the users table")
        assert "DROP TABLE" in sql

    def test_generate_insert(self) -> None:
        sql = self.agent.generate("add a new user")
        assert "INSERT" in sql

    def test_generate_update(self) -> None:
        sql = self.agent.generate("change user email")
        assert "UPDATE" in sql

    def test_generate_select_orders(self) -> None:
        sql = self.agent.generate("find all orders")
        assert "SELECT" in sql
        assert "orders" in sql

    def test_generate_with_guidance_parameterized(self) -> None:
        sql = self.agent.generate("show me users", guidance="use ? placeholders")
        assert "?" in sql

    def test_generate_with_guidance_delete(self) -> None:
        sql = self.agent.generate("delete user 1", guidance="parameterize")
        assert "?" in sql
        assert "DELETE" in sql

    def test_unsafe_has_inline_values(self) -> None:
        sql = self.agent.generate("get user admin")
        assert "'admin'" in sql

    def test_deterministic_same_prompt(self) -> None:
        sql1 = self.agent.generate("show me all users")
        sql2 = self.agent.generate("show me all users")
        assert sql1 == sql2

    def test_deterministic_different_prompt_different_sql(self) -> None:
        sql1 = self.agent.generate("show me users")
        sql2 = self.agent.generate("show me orders")
        assert sql1 != sql2

    def test_empty_prompt_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            self.agent.generate("")

    def test_whitespace_prompt_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            self.agent.generate("   ")

    def test_generate_default(self) -> None:
        sql = self.agent.generate("do something random")
        assert sql is not None
        assert len(sql) > 0

    def test_generate_truncate(self) -> None:
        sql = self.agent.generate("truncate the users table")
        assert "TRUNCATE" in sql

    def test_generate_alter(self) -> None:
        sql = self.agent.generate("alter the users table add column email")
        assert "ALTER" in sql

    def test_generate_products(self) -> None:
        sql = self.agent.generate("get products")
        assert "products" in sql

    def test_generate_safe_select_parameterized(self) -> None:
        sql = self.agent.generate("find users by name", guidance="use ?")
        assert "?" in sql
        assert "SELECT" in sql
        assert "users" in sql

    def test_generate_safe_insert_parameterized(self) -> None:
        sql = self.agent.generate("add new user", guidance="use ?")
        assert "?" in sql
        assert "INSERT" in sql
