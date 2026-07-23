# EvoMind Observability — Testing Strategy

## Testing Principles

1. **Deterministic tests**: Every test produces the same result every time. No flaky tests. No LLM calls.
2. **Component isolation**: Each component is tested in isolation with mocked dependencies.
3. **Trace validation**: Tests verify that telemetry spans have correct attributes — not just functional correctness.
4. **Lifecycle integration**: The full request lifecycle is tested as an integration scenario.
5. **Demo reproducibility**: The exact demo sequence is codified as an acceptance test.

---

## Test Categories

| Category | Scope | Count (estimate) |
|---|---|---|
| Unit tests | Individual component logic | 25-35 |
| Integration tests | Component + SQLite + OTel (mock collector) | 5-8 |
| Deterministic tests | Confidence model with known input sequences | 5 |
| Regression tests | SQL evaluator input/output matrix | 20+ |
| Telemetry validation | Span attributes and metric values | 10 |
| Failure injection | Error handling in every component | 8 |
| Acceptance test | Full lifecycle demo sequence | 1 |

---

## 1. Unit Tests

### SQL Agent

| Test | Input | Expected Output | Verification |
|---|---|---|---|
| generate_no_guidance | prompt="users with id 5", guidance=None | SQL with literal value (unsafe) | SQL contains `5` or similar literal |
| generate_with_guidance | prompt="users with id 5", guidance="use ?" | SQL with `?` placeholder (safe) | SQL contains `?` |
| generate_empty_prompt | prompt="", guidance=None | raises ValueError | |
| generate_guidance_override | prompt="show all", guidance=text | contains guidance text in output metadata | |

### Outcome Evaluator

| Test | Input | Expected Classification |
|---|---|---|
| safe_qmark | `SELECT * FROM users WHERE id = ?` | safe |
| safe_pct_s | `SELECT * FROM users WHERE name = %s` | safe |
| safe_dollar | `SELECT * FROM users WHERE id = $1` | safe |
| unsafe_literal_where | `SELECT * FROM users WHERE id = 123` | unsafe |
| unsafe_literal_string | `SELECT * FROM users WHERE name = 'admin'` | unsafe |
| unsafe_literal_values | `INSERT INTO users VALUES (1, 'test')` | unsafe |
| unsafe_literal_set | `UPDATE users SET name = 'new' WHERE id = 1` | unsafe |
| unsafe_in_literals | `SELECT * FROM users WHERE id IN (1, 2, 3)` | unsafe |
| ambiguous_no_data | `SELECT * FROM users` | ambiguous |
| ambiguous_aggregate | `SELECT COUNT(*) FROM products` | ambiguous |
| ambiguous_mixed | `SELECT * FROM users WHERE id = ? AND name = 'admin'` | ambiguous |
| empty_sql | `` | ValueError |
| null_sql | None | ValueError |
| malformed_sql | `SELECT * FRM users` | EvaluationError |

### Observation Factory

| Test | Input | Expected Evidence Type |
|---|---|---|
| unsafe_no_guidance | classification=unsafe, guidance_injected=false | supporting |
| safe_no_guidance | classification=safe, guidance_injected=false | baseline |
| ambiguous_no_guidance | classification=ambiguous, guidance_injected=false | neutral |
| safe_with_guidance | classification=safe, guidance_injected=true | supporting |
| unsafe_with_guidance | classification=unsafe, guidance_injected=true | contradicting |
| ambiguous_with_guidance | classification=ambiguous, guidance_injected=true | neutral |

### Confidence Engine

| Test | Sequence | Expected Final Confidence |
|---|---|---|
| no_observations | — | 0.50 (prior) |
| one_supporting | [supporting] | 0.67 |
| three_supporting | [supporting, supporting, supporting] | 0.80 |
| one_contradicting | [contradicting] | 0.33 |
| equal_split | [supporting, contradicting, supporting, contradicting] | 0.50 |
| mixed_then_bias | [contradicting, supporting, supporting, supporting] | 0.67 |
| many_supporting | [supporting × 100] | ~0.99 (approaches 1.0) |
| neutral_no_change | [neutral] | 0.50 (unchanged) |
| baseline_no_change | [baseline] | 0.50 (unchanged — baseline does not update α/β) |
| mixed_baseline_and_supporting | [baseline, supporting, baseline, supporting] | 0.67 (only supporting counts) |

### State Machine

| Test | Initial State | Trigger | Expected New State |
|---|---|---|---|
| promote_to_active | candidate, conf=0.80, ev=3 | check_transition | active |
| no_promotion_low_conf | candidate, conf=0.60, ev=3 | check_transition | candidate (no change) |
| no_promotion_low_ev | candidate, conf=0.80, ev=2 | check_transition | candidate (no change) |
| demote_to_suspended | active, conf=0.30 | check_transition | suspended |
| no_demotion_above | active, conf=0.50 | check_transition | active (no change) |
| re_promote | suspended, conf=0.80 | check_transition | active |
| no_transition_archived | archived, any | check_transition | archived |

---

## 2. Integration Tests

### Full Lifecycle (no rule promoted)

1. Seed rule with confidence = 0.50, status = candidate
2. Submit request: `"Show me users with id 5"`
3. Assert: SQL generated with literal
4. Assert: classification = unsafe
5. Assert: evidence_type = supporting
6. Assert: confidence increases (0.50 → 0.67)
7. Assert: status remains candidate (threshold not crossed)
8. Assert: OTel span attributes match expected values

### Full Lifecycle (rule promoted)

1. Seed rule with alpha=4, beta=1, conf=0.80, status=candidate
2. Submit request: `"Show me users with id 5"`
3. Assert: rule retrieved (now active)
4. Assert: guidance injected
5. Assert: SQL generated with `?`
6. Assert: classification = safe
7. Assert: evidence_type = supporting
8. Assert: confidence increases (0.80 → 0.83)
9. Assert: status changed to active in spans

---

## 3. Deterministic Tests (Confidence Model)

These tests verify the exact mathematical behavior of the confidence model.

```
Test: "Confidence update is O(1) and exact"

Given: alpha=1, beta=1
When: supporting evidence added
Then: alpha=2, beta=1, confidence=2/3=0.666...

Given: alpha=2, beta=2
When: contradicting evidence added twice
Then: alpha=2, beta=4, confidence=2/6=0.333...

Given: alpha=1, beta=1, 10 supporting, 5 contradicting
Then: alpha=11, beta=6, confidence=11/17=0.647...
```

---

## 4. Regression Tests (SQL Evaluator)

Complete input/output matrix. See `docs/06_SQL_EVALUATOR.md` — "Testing Matrix" section. Every row in that matrix is a test case.

Additionally:

```
Test: "Classification stability"
Input: "SELECT * FROM users WHERE id = 123"
Run 100 times: Always returns "unsafe"
```

---

## 5. Telemetry Validation

### Span Presence Test

After one request lifecycle, verify all expected spans exist:

```python
expected_spans = [
    "evomind.request",
    "evomind.rule.retrieval",
    "evomind.sql.generation",
    "evomind.sql.evaluation",
    "evomind.observation.created",
    "evomind.evidence.appended",
    "evomind.confidence.updated",
    "evomind.lifecycle.complete",
]

# guidance.injection and rule.state_change are conditional
```

### Attribute Presence Test

For each span, verify that all required attributes are present with correct types.

### Trace Structure Test

Verify parent-child relationships:
- `evomind.request` is root
- All other spans are children of root
- No orphan spans

### Metric Emission Test

After N requests:
- `evomind.requests.total` counter = N
- `evomind.rule.confidence` gauge reflects final confidence

---

## 6. Failure Injection Tests

| Test | Failure Injected | Expected Behavior |
|---|---|---|
| SQL agent fails | Agent raises AgentGenerationError | Orchestrator returns 500, span status = ERROR |
| SQL evaluator crash | Evaluator raises EvaluationError | Orchestrator returns 500, span status = ERROR |
| Database write fails | Evidence store write fails | Orchestrator returns 500, error span event emitted |
| Confidence is NaN | Corrupt alpha/beta values | Confidence treated as 0.0, warning span event |
| Rule not found | Deleted rule_id | Orchestrator catches KeyError, emits warning, continues |
| Empty prompt | User sends empty prompt | Orchestrator returns 400 before creating span |

---

## 7. Acceptance Test: Demo Sequence

The complete demo sequence is codified as a single integration test:

```python
def test_demo_sequence():
    """
    Runs the exact demo flow:
    1. Seed rule with defaults
    2. Submit 3 unsafe requests → confidence 0.80
    3. Verify rule promoted to active
    4. Submit 3 guided requests → confidence 0.86
    5. Verify all SQL is safe after guidance
    6. Verify complete trace structure in mock OTel collector
    """
```

This test must pass before any demo is delivered.

---

## Test Infrastructure

| Tool | Purpose |
|---|---|
| pytest | Test runner |
| pytest-asyncio | Async test support (if FastAPI async handlers) |
| pytest-cov | Coverage reporting |
| sqlite3 (:memory:) | Test database (each test gets fresh DB) |
| unittest.mock | Component mocking |
| opentelemetry-sdk (in-memory exporter) | Telemetry validation without SigNoz |

### In-Memory OTel Exporter

```python
from opentelemetry.sdk.trace.export.in_memory import InMemorySpanExporter

exporter = InMemorySpanExporter()
# Configure SDK to use exporter
# After test: exporter.get_finished_spans()
```

This allows telemetry validation without running SigNoz in CI.

---

## Coverage Target

| Component | Coverage Target |
|---|---|
| Outcome Evaluator | 100% (deterministic, all branches testable) |
| Confidence Engine | 100% (mathematical, no branches) |
| Observation Factory | 100% (finite state table) |
| Guidance Injector | 100% (string operation) |
| Rule Registry (transitions) | 100% (state machine) |
| Orchestrator | 85% (error paths may be hard to trigger) |
| SQL Agent (mock) | 100% (two code paths) |
| Telemetry utilities | 80% |

---

## Non-Testable Items

- SigNoz dashboard correctness (must be verified manually by visual inspection)
- SigNoz installation/deployment (follow SigNoz docs)
- Real LLM integration (not in scope for mock agent)
