from __future__ import annotations

import pytest

from evomind.evaluator.sql_safety_evaluator import SqlSafetyEvaluator
from evomind.models.enums import Classification


class TestSqlSafetyEvaluator:
    def setup_method(self) -> None:
        self.evaluator = SqlSafetyEvaluator()

    def test_safe_simple_select(self) -> None:
        result = self.evaluator.evaluate("SELECT id, name FROM users WHERE id = ?")
        assert result.classification == Classification.SAFE
        assert result.detected_patterns == []

    def test_safe_parameterized_query(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users WHERE id = ? AND name = ?")
        assert result.classification in (Classification.SAFE, Classification.AMBIGUOUS)

    def test_unsafe_drop_table(self) -> None:
        result = self.evaluator.evaluate("DROP TABLE users")
        assert result.classification == Classification.UNSAFE
        assert "dangerous_ddl" in result.detected_patterns

    def test_unsafe_truncate(self) -> None:
        result = self.evaluator.evaluate("TRUNCATE TABLE users")
        assert result.classification == Classification.UNSAFE
        assert "dangerous_ddl" in result.detected_patterns

    def test_unsafe_alter(self) -> None:
        result = self.evaluator.evaluate("ALTER TABLE users DROP COLUMN password")
        assert result.classification == Classification.UNSAFE
        assert "dangerous_ddl" in result.detected_patterns

    def test_unsafe_delete_without_where(self) -> None:
        result = self.evaluator.evaluate("DELETE FROM users")
        assert result.classification == Classification.UNSAFE
        assert "dangerous_dml" in result.detected_patterns

    def test_unsafe_update_without_where(self) -> None:
        result = self.evaluator.evaluate("UPDATE users SET email = 'x'")
        assert result.classification == Classification.UNSAFE
        assert "dangerous_dml" in result.detected_patterns

    def test_safe_delete_with_where(self) -> None:
        result = self.evaluator.evaluate("DELETE FROM users WHERE id = ?")
        assert result.classification == Classification.SAFE
        assert "dangerous_dml" not in result.detected_patterns

    def test_unsafe_string_concat(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users WHERE name = 'admin' + 'test'")
        assert result.classification == Classification.UNSAFE
        assert "sql_injection" in result.detected_patterns

    def test_unsafe_or_tautology(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users WHERE id = 1 OR 1=1")
        assert result.classification == Classification.UNSAFE
        assert "tautology" in result.detected_patterns

    def test_unsafe_union_select(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users UNION SELECT * FROM admins")
        assert result.classification == Classification.UNSAFE
        assert "union_injection" in result.detected_patterns

    def test_unsafe_stacked_queries(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users; DROP TABLE users")
        assert result.classification == Classification.UNSAFE
        assert "stacked_queries" in result.detected_patterns

    def test_unsafe_sleep(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users WHERE id = SLEEP(5)")
        assert "time_based_attack" in result.detected_patterns
        assert result.classification == Classification.UNSAFE

    def test_ambiguous_inline_values(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users WHERE name = 'admin'")
        assert result.classification == Classification.AMBIGUOUS
        assert "inline_values" in result.detected_patterns

    def test_empty_sql_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            self.evaluator.evaluate("")

    def test_none_sql_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            self.evaluator.evaluate("   ")

    def test_select_star_detected(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users WHERE id = ?")
        assert "select_star" in result.detected_patterns

    def test_like_wildcard_prefix(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users WHERE name LIKE '%admin'")
        assert "like_wildcard_prefix" in result.detected_patterns

    def test_sql_comments_detected(self) -> None:
        result = self.evaluator.evaluate("SELECT * FROM users -- comment")
        assert "sql_comments" in result.detected_patterns

    def test_detected_patterns_in_result(self) -> None:
        result = self.evaluator.evaluate("DROP TABLE users")
        assert len(result.detected_patterns) >= 1
        assert len(result.reason) > 0

    def test_insert_without_column_list_is_unsafe(self) -> None:
        result = self.evaluator.evaluate("INSERT INTO users VALUES ('admin', 'pw')")
        assert "dangerous_dml" in result.detected_patterns

    def test_evaluator_confidence_always_1(self) -> None:
        result = self.evaluator.evaluate("SELECT 1")
        assert result.evaluator_confidence == 1.0
