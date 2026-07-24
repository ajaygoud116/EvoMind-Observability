from __future__ import annotations

import re

import sqlparse
from sqlparse.sql import Identifier, TokenList, Where, Comparison
from sqlparse.tokens import DML, DDL, Keyword, Name, Punctuation, Whitespace, Comment

from evomind.exceptions.errors import EvaluationError
from evomind.interfaces.outcome_evaluator import OutcomeEvaluator
from evomind.models.enums import Classification
from evomind.models.evaluation_result import EvaluationResult


UNSAFE_DDL = frozenset({"drop", "truncate", "alter", "create", "rename"})
UNSAFE_DML_MODIFY = frozenset({"delete", "update", "insert", "replace"})
DML_SELECT = frozenset({"select", "pivot", "unpivot"})


class SqlSafetyEvaluator(OutcomeEvaluator):
    """Deterministic, rule-based SQL safety evaluator using sqlparse.

    Detection rules:
    1. Dangerous DDL
    2. Dangerous DML without WHERE
    3. SQL injection via string concatenation
    4. SQL comments inside statements
    5. Stacked queries / multiple statements
    6. LIKE with wildcard prefix
    7. OR 1=1 tautology
    8. SELECT *
    9. Comment-style inline values
    10. Functions in WHERE clauses
    """

    def evaluate(self, sql: str) -> EvaluationResult:
        if not sql or not sql.strip():
            raise ValueError("sql must not be empty")

        try:
            parsed = sqlparse.parse(sql)
        except Exception as exc:
            raise EvaluationError(f"SQL parsing failed: {exc}") from exc

        detected_patterns: list[str] = []
        reasons: list[str] = []
        total_statements = len(parsed)

        if total_statements > 1:
            detected_patterns.append("stacked_queries")
            reasons.append(f"Multiple statements detected ({total_statements})")

        for stmt in parsed:
            stmt_str = str(stmt).strip()
            if not stmt_str:
                continue

            self._check_ddl(stmt, detected_patterns, reasons)
            self._check_dml_without_where(stmt, detected_patterns, reasons)
            self._check_string_concat(stmt_str, detected_patterns, reasons)
            self._check_sql_comments(stmt_str, detected_patterns, reasons)
            self._check_like_wildcard(stmt_str, detected_patterns, reasons)
            self._check_tautology(stmt_str, detected_patterns, reasons)
            self._check_select_star(stmt_str, detected_patterns, reasons)
            self._check_inline_values(stmt_str, detected_patterns, reasons)
            self._check_functions_in_where(stmt_str, detected_patterns, reasons)
            self._check_sleep_benchmark(stmt_str, detected_patterns, reasons)
            self._check_union_injection(stmt_str, detected_patterns, reasons)

        if detected_patterns:
            is_destructive = any(p in detected_patterns for p in
                                 ("dangerous_ddl", "dangerous_dml", "sql_injection",
                                  "stacked_queries", "tautology", "union_injection",
                                  "time_based_attack", "inline_values"))
            if is_destructive:
                classification = Classification.UNSAFE
            else:
                classification = Classification.AMBIGUOUS
        else:
            classification = Classification.SAFE

        return EvaluationResult(
            classification=classification,
            reason="; ".join(reasons) if reasons else "No unsafe patterns detected",
            detected_patterns=detected_patterns,
            evaluator_confidence=1.0,
        )

    def _check_ddl(
        self,
        stmt: sqlparse.sql.Statement,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        for token in stmt.tokens:
            if token.ttype in (DDL, Keyword) and token.value.lower() in UNSAFE_DDL:
                patterns.append("dangerous_ddl")
                reasons.append(f"Dangerous DDL statement: {token.value}")
                return

    def _check_dml_without_where(
        self,
        stmt: sqlparse.sql.Statement,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        dml_type = None
        has_where = False

        for token in stmt.tokens:
            if token.ttype is DML:
                dml_type = token.value.lower()
            if isinstance(token, Where):
                has_where = True

        if dml_type in UNSAFE_DML_MODIFY and not has_where:
            patterns.append("dangerous_dml")
            reasons.append(f"{dml_type.upper()} without WHERE clause")

    def _check_string_concat(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        concat_patterns = [
            r"\+[\s]*'",  # + '
            r"'[\s]*\+",  # ' +
            r"\|\|[\s]*'",  # || '
            r"'[\s]*\|\|",  # ' ||
            r"concat\s*\(",  # CONCAT(
        ]
        for pat in concat_patterns:
            if re.search(pat, stmt_str, re.IGNORECASE):
                patterns.append("sql_injection")
                reasons.append("String concatenation detected")
                return

    def _check_sql_comments(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        if "--" in stmt_str or "/*" in stmt_str:
            patterns.append("sql_comments")
            reasons.append("SQL comment detected in statement")

    def _check_like_wildcard(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        like_matches = re.finditer(
            r"LIKE\s+'%[^']+'",
            stmt_str,
            re.IGNORECASE,
        )
        for match in like_matches:
            patterns.append("like_wildcard_prefix")
            reasons.append(f"LIKE with leading wildcard: {match.group()}")
            return

    def _check_tautology(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        tautology_regexes = [
            r"(?:\d+)\s*=\s*(?:\d+)",       # 1=1, 2=2
            r"'.*?'\s*=\s*'.*?'",             # 'a'='a'
            r"\d+\s*<>\s*\d+",                # 1<>2
            r"\d+\s*!=\s*\d+",                # 1!=2
        ]
        for regex in tautology_regexes:
            if re.search(regex, stmt_str, re.IGNORECASE):
                patterns.append("tautology")
                reasons.append("Always-true tautology in SQL")
                return

    def _check_select_star(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        if re.search(r"SELECT\s+\*", stmt_str, re.IGNORECASE):
            patterns.append("select_star")
            reasons.append("SELECT * used")

    def _check_inline_values(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        if re.search(r"'\d{4}-\d{2}-\d{2}'", stmt_str):
            return
        inline = re.findall(r"'\w+'", stmt_str)
        if len(inline) >= 1:
            patterns.append("inline_values")
            reasons.append(f"Inline string values detected ({len(inline)} values)")

    def _check_functions_in_where(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        funcs = ["substring", "substr", "lower", "upper", "length", "char_length",
                 "hex", "ord", "ascii"]
        for func in funcs:
            if re.search(rf"\b{func}\s*\(", stmt_str, re.IGNORECASE):
                patterns.append("functions_in_where")
                reasons.append(f"Function in SQL: {func}()")
                return

    def _check_sleep_benchmark(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        if re.search(r"\bsleep\s*\(", stmt_str, re.IGNORECASE):
            patterns.append("time_based_attack")
            reasons.append("SLEEP() function detected")
        if re.search(r"\bbenchmark\s*\(", stmt_str, re.IGNORECASE):
            patterns.append("time_based_attack")
            reasons.append("BENCHMARK() function detected")

    def _check_union_injection(
        self,
        stmt_str: str,
        patterns: list[str],
        reasons: list[str],
    ) -> None:
        if re.search(r"UNION\s+(ALL\s+)?SELECT", stmt_str, re.IGNORECASE):
            patterns.append("union_injection")
            reasons.append("UNION SELECT detected")
