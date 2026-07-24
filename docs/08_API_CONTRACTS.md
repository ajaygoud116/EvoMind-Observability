# EvoMind Observability — API Contracts

## Conventions

- All IDs are UUID v4 strings
- All timestamps are ISO 8601 strings (UTC)
- All functions are synchronous unless marked `async`
- Errors are raised as typed exceptions, not generic `Exception`
- Input validation uses Pydantic models (FastAPI integration)
- Return types are `dataclass` or `dict` as specified

---

## 1. Orchestrator Entry Point

### `POST /api/query`

The single public API endpoint.

**Request:**
```json
{
  "prompt": "Show me users with id 123",
  "context": {}  // optional extensions
}
```

**Response:**
```json
{
  "request_id": "req-a1b2c3d4-5678",
  "sql": "SELECT * FROM users WHERE id = ?",
  "classification": "safe",
  "rule_retrieved": true,
  "rule_name": "use_parameterized_sql",
  "guidance_injected": true,
  "confidence": 0.83
}
```

**Errors:**

| Status | Condition |
|---|---|
| 400 | Empty or missing prompt |
| 500 | Internal component failure |

---

## 2. Orchestrator Internal Interface

### `Orchestrator.process_request(prompt: str) -> Response`

The core orchestration method. Called by the `POST /api/query` handler. Owns the OTel trace.

```python
@dataclass
class Response:
    request_id: str
    sql: str
    classification: str
    rule_retrieved: bool
    rule_name: Optional[str]
    guidance_injected: bool
    confidence: float
```

**Steps (in order):**
1. Generate request_id
2. Create root span
3. Call RuleRetriever.retrieve()
4. If rules found, call GuidanceInjector.inject()
5. Call SQLAgent.generate()
6. Call OutcomeEvaluator.evaluate()
7. Call ObservationFactory.create()
8. Call EvidenceStore.append()
9. Call ConfidenceEngine.update()
10. Call rule_repository.check_transition()
11. Emit lifecycle.complete span
12. End root span
13. Return Response

---

## 3. SQL Agent

### `SQLAgent.generate(prompt: str, guidance: Optional[str]) -> str`

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `prompt` | `str` | Natural language request |
| `guidance` | `Optional[str]` | Guidance text to inject (None if no rule retrieved) |

**Output:**
| Type | Description |
|---|---|
| `str` | Generated SQL string |

**Behavior (Mock Agent):**

| Guidance | Behavior |
|---|---|
| None or empty | Always generates unsafe SQL: `SELECT * FROM users WHERE id = 123` (the exact SQL varies with the prompt but always uses literal values) |
| Present | Always generates safe SQL: `SELECT * FROM users WHERE id = ?` |

**Errors:**

| Error | Condition |
|---|---|
| `AgentGenerationError` | Agent fails to produce SQL |
| `ValueError` | `prompt` is empty or None |

**Design Rationale:** The mock agent is deterministic to enable reproducible demos. It can be replaced with a real LLM call behind the same interface without changing any other component.

---

## 4. Outcome Evaluator

### `OutcomeEvaluator.evaluate(sql: str) -> EvaluationResult`

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `sql` | `str` | The SQL string to evaluate |

**Output:**
```python
@dataclass
class EvaluationResult:
    classification: str       # "safe" | "unsafe" | "ambiguous"
    reason: str               # Human-readable explanation
    detected_patterns: list[str]  # e.g., ["literal_in_where:id"]
    evaluator_confidence: float   # Always 1.0
```

**Errors:**

| Error | Condition |
|---|---|
| `ValueError` | `sql` is empty or None |
| `EvaluationError` | sqlparse fails to parse (malformed SQL) |

---

## 5. Observation Factory

### `ObservationFactory.create(evaluation: EvaluationResult, context: RequestContext) -> Observation`

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `evaluation` | `EvaluationResult` | Result from the Outcome Evaluator |
| `context` | `RequestContext` | The current request context (including guidance_injected flag) |

**Output:**
```python
@dataclass
class Observation:
    id: str
    request_id: str
    rule_id: str
    classification: str
    evidence_type: str        # "supporting" | "contradicting" | "baseline" | "neutral"
    sql_generated: Optional[str]
    evaluation_reason: Optional[str]
    metadata: Optional[dict]
    created_at: str
```

**Evidence Type Derivation:**

The derivation depends on whether the rule was active (guidance injected) or not.

| Classification | Guidance Injected? | Evidence Type | Confidence Impact |
|---|---|---|---|
| safe | No | baseline | No update |
| unsafe | No | supporting | α += 1 |
| ambiguous | No | neutral | No update |
| safe | Yes | supporting | α += 1 |
| unsafe | Yes | contradicting | β += 1 |
| ambiguous | Yes | neutral | No update |

**Key semantic:** Safe SQL before rule promotion (no guidance) is "baseline" — it does not decrease confidence because the agent was not yet following the rule. Only after the rule is active and guidance is injected do safe results increase and unsafe results decrease confidence.

**Errors:**

| Error | Condition |
|---|---|
| `ValueError` | `evaluation` is None |
| `ObservationError` | Failed to persist observation |

---

## 6. Evidence Store

### `EvidenceStore.append(observation: Observation) -> EvidenceRecord`

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `observation` | `Observation` | The observation to persist as evidence |

**Output:**
```python
@dataclass
class EvidenceRecord:
    id: str
    observation_id: str
    rule_id: str
    evidence_type: str
    request_id: str
    confidence_before: float
    confidence_after: float
    delta: float
    created_at: str
```

**Errors:**

| Error | Condition |
|---|---|
| `ValueError` | `observation` is None |
| `EvidenceStoreError` | Database write failure |

---

### `EvidenceStore.get_summary(rule_id: str) -> EvidenceSummary`

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `rule_id` | `str` | Rule to summarize |

**Output:**
```python
@dataclass
class EvidenceSummary:
    rule_id: str
    total_count: int
    supporting_count: int
    contradicting_count: int
    neutral_count: int
    first_evidence_at: Optional[str]
    latest_evidence_at: Optional[str]
```

---

## 7. Confidence Engine

### `ConfidenceEngine.update(rule_id: str) -> ConfidenceUpdate`

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `rule_id` | `str` | Rule to update |

**Output:**
```python
@dataclass
class ConfidenceUpdate:
    rule_id: str
    confidence_before: float
    confidence_after: float
    delta: float
    alpha: float
    beta: float
    supporting_count: int
    contradicting_count: int
    status_changed: bool
    from_status: Optional[str]
    to_status: Optional[str]
```

**Algorithm:**
1. Load rule from rule_repository
2. Load latest evidence type from EvidenceStore
3. Update alpha/beta per evidence type
4. Compute new confidence = alpha / (alpha + beta)
5. Check transition conditions
6. Persist updated rule
7. Return ConfidenceUpdate

**Errors:**

| Error | Condition |
|---|---|
| `KeyError` | `rule_id` not found |
| `ConfidenceError` | Computation results in NaN |

---

## 8. Behavioral Rule Repository

### `rule_repository.get_rule(rule_id: str) -> BehavioralRule`

Returns the full BehavioralRule entity.

### `rule_repository.get_active_rules() -> list[BehavioralRule]`

Returns all rules with `status == "active"`.

### `rule_repository.create_rule(name: str, guidance_text: str, **kwargs) -> BehavioralRule`

Creates a new rule with default parameters. Only used for seeding the single rule.

### `rule_repository.update_confidence(rule_id: str, alpha: float, beta: float, confidence: float) -> BehavioralRule`

Updates the Bayesian parameters after ConfidenceEngine computation.

### `rule_repository.check_transition(rule_id: str) -> TransitionResult`

Checks and executes state transitions.

**Output:**
```python
@dataclass
class TransitionResult:
    transitioned: bool
    from_status: Optional[str]
    to_status: Optional[str]
    reason: Optional[str]
```

**Transition Logic:**
```python
if rule.status == "candidate":
    if (rule.confidence >= rule.promotion_threshold 
        and (rule.supporting_count + rule.contradicting_count) >= rule.min_evidence):
        rule.status = "active"
        rule.promoted_at = now()
        return TransitionResult(True, "candidate", "active", "confidence_threshold_met")

elif rule.status == "active":
    if rule.confidence < rule.demotion_threshold:
        rule.status = "suspended"
        rule.demoted_at = now()
        return TransitionResult(True, "active", "suspended", "confidence_below_demotion_threshold")

elif rule.status == "suspended":
    if rule.confidence >= rule.promotion_threshold:
        rule.status = "active"
        rule.promoted_at = now()
        return TransitionResult(True, "suspended", "active", "re_promoted")

return TransitionResult(False, None, None, None)
```

**Errors:**

| Error | Condition |
|---|---|
| `KeyError` | `rule_id` not found |
| `RegistryError` | Database write failure |

---

## 9. Rule Retriever

### `RuleRetriever.retrieve(context: RequestContext) -> list[BehavioralRule]`

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `context` | `RequestContext` | Current request context (for future condition matching) |

**Output:**
| Type | Description |
|---|---|
| `list[BehavioralRule]` | Ordered list of Active rules matching the context. Empty if none. |

For the hackathon, all Active rules match. Future implementations may filter by `condition` field.

**Errors:**

| Error | Condition |
|---|---|
| `RetrievalError` | Registry query fails |

---

## 10. Guidance Injector

### `GuidanceInjector.inject(prompt: str, rules: list[BehavioralRule]) -> str`

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `prompt` | `str` | Original user prompt |
| `rules` | `list[BehavioralRule]` | Active rules to inject |

**Output:**
| Type | Description |
|---|---|
| `str` | Modified prompt with guidance prepended |

**Injection Format:**
```
IMPORTANT GUIDELINES:
• Always use parameterized queries with ? placeholders for all user-supplied values.
• Never use string interpolation, f-strings, or % formatting to embed values in SQL.
• Use parameterized query syntax: WHERE id = ? (not WHERE id = {value}).

Original Request:
{original_prompt}
```

**Errors:**

| Error | Condition |
|---|---|
| `ValueError` | `prompt` is empty |
| `InjectionError` | Prompt modification fails |

---

## 11. Telemetry Layer

The Telemetry Layer is not a standalone component. It is a set of utilities used by the Orchestrator.

### `Telemetry.start_trace(name: str, attributes: dict) -> Span`

Creates and returns a new root span.

### `Telemetry.create_span(name: str, parent: Span, attributes: dict) -> Span`

Creates a child span.

### `Telemetry.end_span(span: Span, attributes: Optional[dict] = None)`

Ends a span, optionally adding final attributes.

### `Telemetry.record_metric(name: str, value: float, attributes: dict)`

Updates or increments a metric.

### `Telemetry.add_event(span: Span, name: str, attributes: dict)`

Adds a span event.

---

## Error Types Summary

```python
class EvoMindError(Exception): pass

class OrchestrationError(EvoMindError): pass
class AgentGenerationError(EvoMindError): pass
class EvaluationError(EvoMindError): pass
class ObservationError(EvoMindError): pass
class EvidenceStoreError(EvoMindError): pass
class ConfidenceError(EvoMindError): pass
class RegistryError(EvoMindError): pass
class RetrievalError(EvoMindError): pass
class InjectionError(EvoMindError): pass
```
