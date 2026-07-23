# EvoMind Observability — SQL Safety Evaluator

## Design Rationale

The SQL Safety Evaluator is **deterministic and rule-based**. It classifies generated SQL without executing it, without an LLM, and without external services. This guarantees:

- **Reproducibility**: Same SQL → same classification, always
- **Zero latency**: No network calls, no model inference
- **Explainability**: Every classification has a specific, traceable reason
- **Testability**: Complete coverage via a known input/output matrix

### Rejected Alternatives

| Approach | Reason for Rejection |
|---|---|
| LLM-as-judge | Non-deterministic. Expensive. Opaque. Contradicts "no meta-agent" principle. |
| Execute SQL against test DB | Security risk. Requires DB setup. Cannot detect injection risk from execution alone. |
| Regex-only | Too brittle. Misses AST-level patterns. High false-positive rate. |
| External API | Dependency. Latency. Cost. No offline demo possible. |

---

## Scope (Frozen)

The SQL Safety Evaluator analyzes **only generated SQL text** — the raw SQL string produced by the agent. It is a purely syntactic analysis.

**The evaluator does NOT inspect:**
- Python source code, AST, or call sites
- ORM queries (SQLAlchemy, Django ORM, etc.)
- Application execution traces or call stacks
- Network traffic or database driver logs
- Any non-SQL artifact

This scope is frozen for the hackathon. The evaluator receives a SQL string and returns a classification. Nothing more.

---

## SQL Privacy

Telemetry may contain sensitive data embedded in SQL strings. A `mask_sql` configuration option controls how SQL appears in OpenTelemetry spans.

| Setting | Effect |
|---|---|
| `mask_sql = false` (default for demo) | Full SQL text is included in span attributes up to truncation limits |
| `mask_sql = true` | SQL text is truncated to first 200 characters; SQL is also SHA-256 hashed; the hash appears in `sql.hash` attribute for cross-trace correlation without exposing data |

**Affected spans:**
| Span | Attribute | Masked Behavior |
|---|---|---|
| `evomind.sql.generation` | `sql.generated` | Truncated to 200 chars; `sql.hash` added |
| `evomind.observation.created` | (via `sql_generated` in Observation) | Same masking applied |
| `evomind.evaluation.details` (span event) | `sql.full` | Omitted when masked |

**How debugging still works:**
1. `request.id` correlates SigNoz traces to local SQLite records
2. Local SQLite stores full unmasked SQL for engineering access
3. The SHA-256 hash allows matching identical SQL across traces without exposing the content

---

## Supported SQL Dialect

The evaluator is dialect-agnostic with `sqlparse`. It does not assume a specific SQL dialect (MySQL, PostgreSQL, SQLite, etc.). It operates on patterns common across all dialects:

- `?` placeholder (SQLite, PostgreSQL via libpq)
- `%s` placeholder (psycopg2, mysql-connector-python)
- `:name` placeholder (Oracle, some PostgreSQL drivers)
- `%(name)s` placeholder (psycopg2 named parameters)
- `$1`, `$2` etc. positional placeholders (PostgreSQL native)
- Literal numbers and strings in data positions

---

## Supported Driver Patterns (for reference)

The evaluator analyzes generated SQL text, not the Python code that produced it. The following driver patterns produce SQL that the evaluator can classify:

| Driver | Safe Pattern | Unsafe Pattern |
|---|---|---|
| sqlite3 | `WHERE id = ?` | `WHERE id = 123` |
| psycopg2 | `WHERE id = %s` | `WHERE id = {value}` |
| MySQLdb | `WHERE id = %s` | f`WHERE id = {value}` |
| asyncpg | `WHERE id = $1` | `WHERE id = ' + str(val) + '` |

---

## Classification Output

```python
@dataclass
class EvaluationResult:
    classification: str  # "safe" | "unsafe" | "ambiguous"
    reason: str          # Human-readable explanation
    detected_patterns: list[str]  # e.g., ["literal_in_where", "no_placeholder"]
    evaluator_confidence: float   # Always 1.0 (deterministic)
```

---

## Detection Rules (in priority order)

The evaluator applies rules in order. The **first matching rule** determines the classification.

### Safe Patterns (classification = "safe")

| # | Rule | Pattern | Example | Reason |
|---|---|---|---|---|
| S1 | Uses `?` placeholder | SQL contains `=` followed by `?` | `SELECT * FROM users WHERE id = ?` | Parameterized query |
| S2 | Uses `%s` placeholder | SQL contains `%s` as value | `INSERT INTO users VALUES (%s, %s)` | Parameterized query (psycopg2 style) |
| S3 | Uses `$N` placeholder | SQL contains `$` followed by digits as value | `SELECT * FROM users WHERE id = $1` | PostgreSQL positional parameter |
| S4 | Uses `:name` placeholder | SQL contains `:` followed by identifier as value | `SELECT * FROM users WHERE id = :user_id` | Named parameter (Oracle, psycopg2) |
| S5 | Uses `%(name)s` placeholder | SQL contains `%(` identifier `)s` | `SELECT * FROM users WHERE id = %(user_id)s` | Named parameter (psycopg2) |

### Unsafe Patterns (classification = "unsafe")

| # | Rule | Pattern | Example | Reason |
|---|---|---|---|---|
| U1 | Literal number in WHERE clause | WHERE comparison has numeric literal on value side | `WHERE id = 123` or `WHERE age > 18` | Value should be parameterized |
| U2 | Literal string in WHERE clause | WHERE comparison has string literal on value side | `WHERE name = 'admin'` | Value should be parameterized |
| U3 | Literal number in VALUES clause | INSERT VALUES contains numeric literal | `VALUES (1, 'foo')` | Value should be parameterized |
| U4 | Literal string in VALUES clause | INSERT VALUES contains string literal | `VALUES (123, 'admin')` | Value should be parameterized |
| U5 | Literal in SET clause | UPDATE SET contains literal value | `SET price = 100 WHERE id = 1` | Value should be parameterized |
| U6 | IN clause with literals | `WHERE id IN (1, 2, 3)` | Multiple literals in IN list | Should use parameters or subquery |
| U7 | String concatenation in SQL | SQL contains `'...' + ...` or `'...' \|\| ...` | `WHERE name = 'prefix' + input` | Dynamic concatenation is injection risk |

### Ambiguous (classification = "ambiguous")

| # | Rule | Example | Reason |
|---|---|---|---|
| A1 | No literals and no placeholders | `SELECT * FROM users` | Simple query with no user-supplied values — cannot determine safety pattern |
| A2 | No WHERE/VALUES/SET clause | `SELECT COUNT(*) FROM users` | No data-dependent values to parameterize |
| A3 | Mixed patterns | `WHERE id = ? AND name = 'admin'` | Some parameters and some literals — mixed approach |

---

## Detection Algorithm

```
function evaluate(sql: str) -> EvaluationResult:
    parsed = sqlparse.parse(sql)
    
    patterns_detected = []
    
    // Check safe patterns first (they are explicit intent)
    if contains_placeholder(parsed, "?"):
        patterns_detected.append("uses_placeholder_qmark")
        if has_any_literal(parsed):
            patterns_detected.append("mixed_placeholders_and_literals")
            return EvaluationResult("ambiguous", "Mixed placeholders and literals", ...)
        return EvaluationResult("safe", "Uses ? parameterized queries", ...)
    
    if contains_placeholder(parsed, "%s"):
        ... (similar logic)
    
    if contains_placeholder(parsed, "$"):
        ... (similar logic)
    
    // Check unsafe patterns
    literals = find_literals_in_data_positions(parsed)
    if literals:
        patterns_detected.extend(literals)
        return EvaluationResult("unsafe", f"Literal values found: {literals}", ...)
    
    // No placeholders, no literals in data positions
    return EvaluationResult("ambiguous", "No placeholders or literals detected", ...)
```

---

## SQL Parsing Approach (sqlparse)

```
function find_literals_in_data_positions(parsed):
    results = []
    for token in parsed.tokens:
        if is_where_clause(token):
            for comparison in extract_comparisons(token):
                if is_literal(comparison.right):
                    results.append(f"literal_in_where:{comparison.left}")
        
        if is_insert_statement(parsed):
            for value in extract_values_clause(parsed):
                if is_literal(value):
                    results.append(f"literal_in_values")
        
        if is_update_statement(parsed):
            for assignment in extract_set_clause(parsed):
                if is_literal(assignment.right):
                    results.append(f"literal_in_set:{assignment.left}")
    
    return results
```

---

## Adversarial Cases

| Input | Classification | Rationale |
|---|---|---|
| `SELECT * FROM users WHERE id = 0x7f` | unsafe | Hex literal is still a literal |
| `SELECT * FROM users WHERE id = NULL` | safe | NULL is not an injection vector |
| `SELECT * FROM users WHERE id = ? -- comment` | safe | Placeholder present, comment ignored |
| `SELECT 1` | ambiguous | No user data involved |
| `SELECT 'hello' AS greeting` | safe | String literal in SELECT, not WHERE/VALUES |
| `DELETE FROM users WHERE id = 5` | unsafe | Literal in WHERE |
| `DELETE FROM users WHERE id = ?` | safe | Parameterized DELETE |

---

## False Positive Analysis

| Case | Classification | False? | Explanation |
|---|---|---|---|
| `SELECT * FROM users WHERE status = 'active'` | unsafe | False positive | String literal where a constant makes sense. However, the system cannot distinguish constants from user-supplied values without schema knowledge. This is acceptable — the guidance "always parameterize" is conservative. |
| `INSERT INTO logs (event, timestamp) VALUES ('login', datetime('now'))` | unsafe | False positive | Function call as value, not a literal. The evaluator should detect function calls and not flag them. |
| `SELECT * FROM users WHERE id IN (SELECT user_id FROM active_users)` | ambiguous | Correct | Subquery, not literals. The evaluator should not flag IN with subqueries. |

---

## False Negative Analysis

| Case | Classification | False? | Explanation |
|---|---|---|---|
| `cursor.execute("SELECT * FROM users WHERE id = " + user_input)` | N/A | False negative | The evaluator analyzes the SQL string, not the code that builds it. If the SQL contains the resolved value (e.g., `WHERE id = 123`), it WILL be caught as unsafe. If the SQL contains a placeholder AND the interpolation is done before execution, it cannot be detected from SQL alone. This is acceptable — we evaluate the generated SQL, not the calling code. |
| `query = "SELECT * FROM users WHERE id = %s" % (user_input,)` | safe → false | False negative | The SQL string contains `%s` which the evaluator classifies as safe. But the Python code uses `%` formatting which is vulnerable before passing to the DB driver. This is a known limitation — the evaluator only checks the SQL text. Documentation should note this. |

---

## Implementation Specification

```python
# Signature
def evaluate_sql(sql: str) -> EvaluationResult:
    """
    Evaluate a SQL string for safety.
    
    Args:
        sql: The SQL string to evaluate.
        
    Returns:
        EvaluationResult with classification, reason, and detected patterns.
        
    Raises:
        ValueError: If sql is empty or None.
    """
```

The implementation uses `sqlparse` to parse the SQL into a token tree, then walks the tree to find placeholders and literals in data positions. No SQL is executed. No network calls are made.

---

## Testing Matrix (see Testing Strategy for full details)

| SQL Input | Expected Classification |
|---|---|
| `SELECT * FROM users WHERE id = ?` | safe |
| `SELECT * FROM users WHERE id = %s` | safe |
| `SELECT * FROM users WHERE id = $1` | safe |
| `SELECT * FROM users WHERE id = 123` | unsafe |
| `SELECT * FROM users WHERE name = 'admin'` | unsafe |
| `INSERT INTO users VALUES (1, 'test')` | unsafe |
| `UPDATE users SET name = 'new' WHERE id = 1` | unsafe |
| `SELECT * FROM users WHERE id IN (1, 2, 3)` | unsafe |
| `SELECT * FROM users` | ambiguous |
| `SELECT COUNT(*) FROM products` | ambiguous |
| `SELECT * FROM users WHERE id = ? AND name = 'admin'` | ambiguous |
| `SELECT datetime('now')` | ambiguous |
| `SELECT * FROM users WHERE id = ? AND name = ?` | safe |
| `DELETE FROM items WHERE id = ?` | safe |
| `CREATE TABLE test (id INT)` | safe (DDL) |
