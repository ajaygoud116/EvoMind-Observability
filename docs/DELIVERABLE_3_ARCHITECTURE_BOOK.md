# Deliverable 3: Architecture Book

**Project:** EvoMind Observability  
**Status:** Architecture Frozen — Permanent Reference  
**Purpose:** Self-contained reference for any engineer joining the project  
**Version:** 0.1.0

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Component Specifications](#3-component-specifications)
4. [Data Models](#4-data-models)
5. [State Machines](#5-state-machines)
6. [Confidence Model Specification](#6-confidence-model-specification)
7. [API Contracts](#7-api-contracts)
8. [Telemetry Specification](#8-telemetry-specification)
9. [Database Schema](#9-database-schema)
10. [Infrastructure Architecture](#10-infrastructure-architecture)
11. [Testing Architecture](#11-testing-architecture)
12. [Learning Lifecycle Walkthrough](#12-learning-lifecycle-walkthrough)
13. [Configuration Reference](#13-configuration-reference)
14. [Exception Reference](#14-exception-reference)
15. [Glossary](#15-glossary)

---

## 1. System Overview

EvoMind Observability is a behavioral learning system for AI agents. It implements a closed feedback loop:

1. A user sends a request to the AI agent
2. The system evaluates the agent's output for behavioral safety
3. The system accumulates evidence about the agent's behavior
4. A confidence engine tracks the system's belief in each behavioral rule
5. Rules that exceed a confidence threshold are promoted and their guidance is injected into future requests
6. The entire lifecycle is instrumented with OpenTelemetry traces and metrics

**Vertical slice:** One agent (SQL assistant), one domain (SQL generation), one behavioral rule ("use parameterized queries"), one observability pipeline (OpenTelemetry → SigNoz).

**Architecture principle:** All components are pluggable via abstract interfaces. The orchestrator is the sole coordinator. No component communicates with any other component directly.

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                        │
│  GET /api/health                              POST /api/query  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼─────────────────────────────────────┐
│                   Orchestrator Pipeline                         │
│                                                                 │
│  1. Validate prompt                ← RequestContext created     │
│  2. Open root span                                             │
│  3. Retrieve rules                 → RuleRetriever             │
│  4. Inject guidance (conditional)  → GuidanceInjector          │
│  5. Generate SQL                   → SQLAgent                  │
│  6. Sanitize SQL (if mask_sql)     → SHA-256 hash              │
│  7. Evaluate SQL                   → SqlSafetyEvaluator        │
│  8. Create observation             → ObservationFactory        │
│  9. Persist request + observation  → RequestContextRepository  │
│ 10. Append evidence                → EvidenceStore             │
│ 11. Update confidence              → ConfidenceEngine          │
│                                                                 │
│  All steps emit OpenTelemetry spans                             │
└──────┬──────────────────────┬──────────────────────┬────────────┘
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   SQLite DB  │    │  OTel Exporter   │    │  MetricsRegistry │
│   (5 tables) │    │  (OTLP gRPC)     │    │  (4 instruments) │
└──────────────┘    └────────┬─────────┘    └──────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  SigNoz Stack    │
                    │  (Collector →    │
                    │   ClickHouse →   │
                    │   Frontend)      │
                    └──────────────────┘
```

---

## 3. Component Specifications

### 3.1 Service Registry (DI Container)

**File:** `evomind/orchestration/service_registry.py`

```python
class ServiceRegistry:
    _services: dict[str, Any]

    def register(key: str, service: Any) -> None
        # Raises ServiceRegistrationError if key already registered

    def resolve(key: str) -> Any
        # Raises ServiceRegistrationError if key not found
```

**Registered keys (all registered at startup):**

| Key | Class |
|---|---|
| `"agent"` | `DeterministicSQLAgent` |
| `"evaluator"` | `SqlSafetyEvaluator` |
| `"observation_factory"` | `ObservationFactory` |
| `"rule_retriever"` | `RuleRetriever` |
| `"guidance_injector"` | `GuidanceInjector` |
| `"evidence_store"` | `EvidenceStore` |
| `"confidence_engine"` | `ConfidenceEngine` |

### 3.2 Orchestrator

**File:** `evomind/orchestration/orchestrator.py`

```python
class Orchestrator:
    def process_request(self, prompt: str, mask_sql: bool = False) -> RequestContext
```

**Input validation:**
- `prompt` must be non-empty and non-whitespace
- Raises `OrchestrationError` if invalid

**Step-by-step span emission:**

| # | Step | Span Name | Conditional | Duration Type |
|---|---|---|---|---|
| 1 | Validate | (root: evomind.request) | — | Pipeline |
| 2 | Retrieve rules | evomind.orchestrator.retrieve_rules | — | DB query |
| 3 | Inject guidance | evomind.orchestrator.inject_guidance | Only if rules found | Memory |
| 4 | Generate SQL | evomind.agent.generate | — | Agent call |
| 5 | Sanitize SQL | (attribute on root span) | Only if mask_sql=True | Hash |
| 6 | Evaluate | evomind.evaluator.evaluate | — | AST parse |
| 7 | Create observation | evomind.observation.create | — | Memory |
| 8 | Persist request | evomind.evidence.persist_request | — | DB write |
| 9 | Persist observation | evomind.evidence.persist_observation | — | DB write |
| 10 | Append evidence | evomind.evidence.append | — | DB R/W + update |
| 11 | State change | evomind.learning.state_change | Only if status changed | DB write |
| 12 | Complete | evomind.lifecycle.complete | — | Memory |

**Error handling:**
- Catches `EvoMindError` subclasses → re-raises as-is
- Catches generic `Exception` → wraps in `OrchestrationError`
- Sets span status to ERROR and records exception
- Database writes are NOT rolled back on failure

### 3.3 Lifecycle Manager

**File:** `evomind/orchestration/lifecycle.py`

```python
class LifecycleManager:
    def startup(self) -> None
    def shutdown(self) -> None
    def resolve(self, key: str) -> Any
```

**Startup order (5 steps):**

1. `TracerManager.initialize(settings, exporter)`
   - Creates `TracerProvider` with versioned resource attributes
   - Creates `BatchSpanProcessor` with max_queue_size=2048, max_export_batch_size=512
   - Registers as global `trace.set_tracer_provider()`

2. `MeterManager.initialize(settings)`
   - Creates `MeterProvider` with service name/version
   - Registers as global `metrics.set_meter_provider()`

3. `MetricsRegistry.reset(meter)`
   - Creates 4 instruments (1 counter, 3 observable gauges)
   - Registers gauge callbacks

4. `Database.initialize(db_path)`
   - Opens SQLite connection with WAL + FK
   - Thread-local connection storage

5. `Schema.create_tables(connection)`
   - Executes 5 CREATE TABLE IF NOT EXISTS statements
   - Executes 6 CREATE INDEX IF NOT EXISTS statements

6. `Seed.seed(connection)`
   - INSERT OR IGNORE default behavioral rule
   - Rule name: "use parameterized queries"
   - Initial status: CANDIDATE, confidence: 0.5

7. `ServiceRegistry.register_all(database)`
   - Creates all repository instances
   - Creates all service instances with dependencies
   - Creates Orchestrator last (depends on all services)

8. Emit startup spans
   - `evomind.system.startup` (root)
   - `evomind.rule.created` (one per seeded rule)

**Shutdown order (reverse):**
1. `TracerManager.shutdown()` — flushes + shutdowns span processor (5s timeout)
2. `MeterManager.shutdown()` — shutdowns meter provider
3. `Database.close()` — closes SQLite connection

### 3.4 SQL Agent

**File:** `evomind/agent/deterministic_agent.py`

```python
class DeterministicSQLAgent(SQLAgent):
    _patterns: dict[str, str]  # 4 regex→SQL template mappings

    def generate(prompt: str, guidance: str | None = None) -> str
```

**Behavior:**
- Lowercases prompt
- Iterates `_patterns` items; first regex match wins
- If `guidance` is provided → uses `?` placeholders (SAFE)
- If `guidance` is None → uses inline literal values (UNSAFE)
- If no pattern matches → returns `"SELECT 1"` (SAFE)

**Pattern table:**

| Regex | Template (no guidance) | Template (guidance) |
|---|---|---|
| `\bselect\b.*\bfrom\b` | `SELECT * FROM {table} WHERE id = 123` | `SELECT * FROM {table} WHERE id = ?` |
| `\binsert\b` | `INSERT INTO {table} (name, email, role, status) VALUES ('Alice', 'alice@example.com', 'admin', 'active')` | `INSERT INTO {table} (name, email, role, status) VALUES (?, ?, ?, ?)` |
| `\bupdate\b` | `UPDATE {table} SET name = 'Alice', email = 'alice@example.com', role = 'admin', status = 'active' WHERE id = 123` | `UPDATE {table} SET name = ?, email = ?, role = ?, status = ? WHERE id = ?` |
| `\bdelete\b` | `DELETE FROM {table} WHERE id = 123` | `DELETE FROM {table} WHERE id = ?` |

### 3.5 SQL Safety Evaluator

**File:** `evomind/evaluator/sql_safety_evaluator.py`

```python
class SqlSafetyEvaluator(OutcomeEvaluator):
    DANGEROUS_DDL: list[str] = ["DROP", "TRUNCATE", "ALTER", "CREATE TABLE", ...]
    DANGEROUS_DML_NO_WHERE: list[str] = ["UPDATE", "DELETE FROM"]

    def evaluate(sql: str, context: dict | None = None) -> EvaluationResult
```

**Detection rules (evaluated in order):**

| # | Rule | Detection Method | Classification |
|---|---|---|---|
| 1 | Dangerous DDL | String match in `DANGEROUS_DDL` list | UNSAFE |
| 2 | Dangerous DML without WHERE | String match + `WHERE` absence check | UNSAFE |
| 3 | String concatenation | Detect `string_agg` or `+` operator | UNSAFE |
| 4 | SQL comments | Detect `--` or `#` in statement | UNSAFE |
| 5 | Stacked queries | Detect `;` separator | UNSAFE |
| 6 | LIKE with wildcard prefix | Detect `LIKE '...%'` (initial wildcard) | UNSAFE |
| 7 | Tautologies | Detect `1=1`, `true`, `1=1 OR 1=1` | UNSAFE |
| 8 | Inline literal values | sqlparse AST: detect `Integer`/`String` tokens | UNSAFE |
| 9 | `SELECT *` / `COUNT(*)` | sqlparse AST: check identifier list for `*` | AMBIGUOUS |
| 10 | Functions in WHERE | sqlparse AST: check WHERE subtree for functions | AMBIGUOUS |
| 11 | Sleep/Benchmark | Detect `SLEEP`, `BENCHMARK` | UNSAFE |
| 12 | UNION injection | Detect `UNION` | AMBIGUOUS |

**Return value:**
- `classification`: SAFE, UNSAFE, or AMBIGUOUS
- `reason`: Concatenated string of detected pattern descriptions
- `patterns_detected`: List of pattern names (e.g., `["inline_literals", "ddl_detected"]`)

### 3.6 Observation Factory

**File:** `evomind/observation/observation_factory.py`

```python
class ObservationFactory(ObservationFactory):
    def create(evaluation: EvaluationResult, rule_id: str,
               request_id: str, sql: str, guidance_injected: bool) -> Observation
```

**Evidence type derivation matrix:**

| Guidance Injected | Classification | Evidence Type | Semantic |
|---|---|---|---|
| No | UNSAFE | SUPPORTING | Rule was needed |
| No | SAFE | BASELINE | No signal (agent was safe) |
| No | AMBIGUOUS | NEUTRAL | No signal |
| Yes | SAFE | SUPPORTING | Rule worked |
| Yes | UNSAFE | CONTRADICTING | Rule failed |
| Yes | AMBIGUOUS | NEUTRAL | No signal |

**Metadata stored on observation:**
```json
{
  "patterns_detected": ["inline_literals", "ddl_detected"]
}
```

### 3.7 Evidence Store

**File:** `evomind/learning/evidence_store.py`

```python
class EvidenceStore(EvidenceStore):
    def __init__(self, rule_repo, evidence_repo, learning_state_repo, confidence_engine)

    def append(observation: Observation) -> EvidenceRecord
```

**Append sequence:**
1. Find rule by `observation.rule_id`
2. Read `confidence_before = rule.confidence`
3. Call `confidence_engine.update(rule_id, evidence_type)` → mutates rule in DB
4. Re-read rule from DB to get updated confidence
5. Calculate `delta = confidence_after - confidence_before`
6. Save `EvidenceRecord` with before/after/delta
7. Save `LearningState` snapshot
8. Return `EvidenceRecord`

**Error conditions:**
- `rule_id` not found → `EvidenceStoreError`
- Database write failure → propagates `DatabaseError`

### 3.8 Confidence Engine

**File:** `evomind/learning/confidence_engine.py`

```python
class ConfidenceEngine(ConfidenceEngine):
    def __init__(self, rule_repo: BehavioralRuleRepository)

    def update(rule_id: str, evidence_type: EvidenceType) -> tuple[float, RuleStatus | None]
```

**Update logic:**

```
def update(rule_id, evidence_type):
    rule = repo.find_by_id(rule_id)
    alpha, beta = rule.alpha, rule.beta

    if evidence_type == SUPPORTING:
        alpha += 1
    elif evidence_type == CONTRADICTING:
        beta += 1
    # BASELINE, NEUTRAL: no change

    confidence = alpha / (alpha + beta)
    new_status = evaluate_state_transition(rule.status, confidence,
                                           total_evidence, evidence_type,
                                           supporting_count, contradicting_count)

    repo.update_confidence(rule_id, confidence, alpha, beta, new_status)
    if new_status and new_status != rule.status:
        repo.update_status(rule_id, new_status)  # increments version

    return confidence, new_status
```

**State transition function:**

```
evaluate_state_transition(status, confidence, total_evidence,
                          evidence_type, supporting_count, contradicting_count):

    match status:
        case CANDIDATE:
            if confidence >= promotion_threshold AND total_evidence >= min_evidence:
                return ACTIVE
            return None  # no transition

        case ACTIVE:
            if confidence < demotion_threshold:
                return SUSPENDED
            return None

        case SUSPENDED:
            if confidence >= promotion_threshold:
                return ACTIVE  # re-promotion
            if evidence_type == CONTRADICTING AND contradicting_count > supporting_count:
                return ARCHIVED
            return None

        case ARCHIVED:
            return None  # terminal state
```

### 3.9 Rule Retriever

**File:** `evomind/learning/rule_retriever.py`

```python
class RuleRetriever(RuleRetriever):
    def __init__(self, repository: BehavioralRuleRepository)

    def retrieve(context: RequestContext) -> list[BehavioralRule]
        return self._repository.find_active()
```

Currently returns ALL active rules. The `context` parameter is reserved for future prompt-matching logic.

### 3.10 Guidance Injector

**File:** `evomind/learning/guidance_injector.py`

```python
class GuidanceInjector(GuidanceInjector):
    INJECTION_FORMAT = "{guidance_text}\n\n---\nUser Query: {prompt}"

    def inject(prompt: str, rule: BehavioralRule) -> str
        return self.INJECTION_FORMAT.format(
            guidance_text=rule.guidance_text,
            prompt=prompt,
        )
```

**Example output:**
```
When generating SQL, always use parameterized queries with ? placeholders instead of inline values. Do not include user input directly in SQL strings.

---
User Query: show me users
```

---

## 4. Data Models

### 4.1 BehavioralRule

```python
@dataclass
class BehavioralRule:
    id: str                      # UUID v4
    name: str                    # Unique human-readable name
    guidance_text: str           # Text prepended to prompts
    status: RuleStatus           # candidate|active|suspended|archived
    confidence: float            # [0.0, 1.0] — Beta distribution mean
    alpha: float                 # > 0 — Beta α parameter
    beta: float                  # > 0 — Beta β parameter
    promotion_threshold: float   # Default: 0.75
    demotion_threshold: float    # Default: 0.35
    min_evidence: int            # Default: 3
    supporting_count: int        # Lifetime supporting evidence count
    contradicting_count: int     # Lifetime contradicting evidence count
    version: int                 # Monotonic state transition counter
    created_at: str              # ISO 8601
    updated_at: str              # ISO 8601
```

**Invariants:**
- `alpha > 0` and `beta > 0` (enforced by DB CHECK)
- `0 <= confidence <= 1` (enforced by DB CHECK)
- `supporting_count >= 0`, `contradicting_count >= 0`
- `version >= 1`, incremented by 1 on each state transition

### 4.2 RequestContext

```python
@dataclass
class RequestContext:
    id: str                      # UUID v4
    prompt: str                  # Original user prompt
    sql_generated: str           # SQL from agent
    guidance_injected: bool      # Whether guidance was used
    rule_retrieved_id: str | None  # ID of retrieved rule
    rule_retrieved: bool         # Whether any rule was found
    classification: Classification  # safe|unsafe|ambiguous
    trace_id: str                # OTel trace ID (hex)
    created_at: str | None       # ISO 8601
```

### 4.3 Observation

```python
@dataclass
class Observation:
    id: str | None               # UUID v4; None before persistence
    request_id: str              # FK → request_contexts.id
    rule_id: str                 # FK → behavioral_rules.id
    classification: Classification  # safe|unsafe|ambiguous
    evidence_type: EvidenceType  # supporting|contradicting|baseline|neutral
    sql_generated: str           # The SQL that was evaluated
    evaluation_reason: str       # Human-readable reason from evaluator
    metadata: dict | None        # Arbitrary additional data (JSON)
    created_at: str | None       # ISO 8601
```

### 4.4 EvaluationResult

```python
@dataclass
class EvaluationResult:
    classification: Classification  # safe|unsafe|ambiguous
    reason: str                     # Evaluator's human-readable reason
    patterns_detected: list[str]    # List of pattern names detected
```

This is a transient value object — NOT persisted directly. The `reason` and `patterns_detected` are stored on the `Observation`.

### 4.5 EvidenceRecord

```python
@dataclass
class EvidenceRecord:
    id: str | None               # UUID v4; None before persistence
    observation_id: str          # FK → observations.id
    rule_id: str                 # FK → behavioral_rules.id
    evidence_type: EvidenceType  # supporting|contradicting|baseline|neutral
    request_id: str              # FK → request_contexts.id
    confidence_before: float     # Rule confidence before this evidence
    confidence_after: float      # Rule confidence after this evidence
    delta: float                 # confidence_after - confidence_before
    created_at: str | None       # ISO 8601
```

**This is the most important tracking record.** The `delta` field enables direct quantification of how much a single observation shifted system confidence. A `delta` of 0 means the evidence was BASELINE or NEUTRAL.

### 4.6 LearningState

```python
@dataclass
class LearningState:
    id: str | None               # UUID v4; None before persistence
    request_id: str              # FK → request_contexts.id
    rule_id: str                 # FK → behavioral_rules.id
    confidence: float            # [0.0, 1.0]
    status: RuleStatus           # candidate|active|suspended|archived
    supporting_count: int        # At snapshot time
    contradicting_count: int     # At snapshot time
    total_evidence: int          # supporting + contradicting
    snapshot_at: str | None      # ISO 8601
```

Created after every evidence append. Enables time-series queries: `SELECT * FROM learning_states WHERE rule_id = ? ORDER BY snapshot_at`.

### 4.7 Enums

```python
class RuleStatus(str, Enum):
    CANDIDATE = "candidate"     # Initial state, evidence being collected
    ACTIVE    = "active"        # Retrieved, guidance injected
    SUSPENDED = "suspended"     # Not retrieved, eligible for re-promotion
    ARCHIVED  = "archived"      # Terminal, permanently retired

class EvidenceType(str, Enum):
    SUPPORTING    = "supporting"     # Rule is needed or worked
    CONTRADICTING = "contradicting"  # Rule failed
    BASELINE      = "baseline"       # Pre-promotion safe (no signal)
    NEUTRAL       = "neutral"        # Ambiguous classification (no signal)

class Classification(str, Enum):
    SAFE      = "safe"       # No dangerous patterns detected
    UNSAFE    = "unsafe"     # Destructive patterns detected
    AMBIGUOUS = "ambiguous"  # Non-destructive patterns detected
```

---

## 5. State Machines

### 5.1 Rule Status State Machine

```
                     ┌─────────────────────┐
                     │                     │
                     ▼                     │
              ┌──────────────┐             │
        ┌────►│   CANDIDATE   │────────────┘
        │     │  (evidence)   │  confidence >= 0.75
        │     └──────────────┘  AND evidence >= 3
        │              │
        │              │ (re-promotion)
        │              ▼  confidence >= 0.75
        │     ┌──────────────┐
        │     │    ACTIVE    │──────────────┐
        │     │  (guidance   │              │
        │     │   injected)  │◄─────────────┤
        │     └──────────────┘              │
        │              │                    │
        │              │ confidence < 0.35  │
        │              ▼                    │
        │     ┌──────────────┐              │
        │     │  SUSPENDED   │──────────────┘
        │     │ (not used)   │
        │     └──────┬───────┘
        │            │
        │            │ CONTRADICTING evidence
        │            │ AND contradicting > supporting
        │            ▼
        │     ┌──────────────┐
        └────►│   ARCHIVED   │ (terminal)
              └──────────────┘
```

**State transition conditions (formal):**

| From | To | Condition |
|---|---|---|
| CANDIDATE | ACTIVE | `confidence >= promotion_threshold AND total_evidence >= min_evidence` |
| ACTIVE | SUSPENDED | `confidence < demotion_threshold` |
| SUSPENDED | ACTIVE | `confidence >= promotion_threshold` |
| SUSPENDED | ARCHIVED | `evidence_type == CONTRADICTING AND contradicting_count > supporting_count` |
| Any | Any | No other transitions |

### 5.2 Evidence Type Derivation (Semantic State Machine)

```
Input: (classification, guidance_injected)

guidance_injected = False:
    classification = UNSAFE    → evidence_type = SUPPORTING
    classification = SAFE      → evidence_type = BASELINE
    classification = AMBIGUOUS → evidence_type = NEUTRAL

guidance_injected = True:
    classification = SAFE      → evidence_type = SUPPORTING
    classification = UNSAFE    → evidence_type = CONTRADICTING
    classification = AMBIGUOUS → evidence_type = NEUTRAL
```

### 5.3 Confidence Update State Machine

```
Input: (evidence_type, alpha, beta)

evidence_type = SUPPORTING:
    alpha' = alpha + 1

evidence_type = CONTRADICTING:
    beta' = beta + 1

evidence_type = BASELINE | NEUTRAL:
    alpha' = alpha
    beta' = beta

confidence' = alpha' / (alpha' + beta')
```

---

## 6. Confidence Model Specification

### 6.1 Mathematical Model

The confidence model is a Beta-Bernoulli conjugate model:

**Prior:** `Beta(α₀=1.0, β₀=1.0)` — the uniform distribution on [0, 1], encoding no prior belief about rule effectiveness.

**Likelihood:** Each observation is a Bernoulli trial. Supporting evidence is a "success" (head: 1). Contradicting evidence is a "failure" (tail: 0).

**Posterior:** `Beta(α₀ + successes, β₀ + failures)` = `Beta(α₀ + supporting_count, β₀ + contradicting_count)`

**Posterior mean (confidence):** `E[Beta(α, β)] = α / (α + β)`

**Posterior variance:** `Var[Beta(α, β)] = αβ / ((α+β)²(α+β+1))`

**Prior sample size:** `α₀ + β₀ = 2`. This is the effective sample size, determining how many observations are needed to overcome the prior. With the uniform prior, approximately 2 observations are needed to meaningfully shift confidence from 0.50.

### 6.2 Update Rules

| Evidence Type | α Update | β Update | α+β Update |
|---|---|---|---|
| SUPPORTING | `α += 1` | — | +1 |
| CONTRADICTING | — | `β += 1` | +1 |
| BASELINE | — | — | 0 |
| NEUTRAL | — | — | 0 |

### 6.3 Example Trajectories

**Rule is effective (promoted to active):**

| Step | Classification | Guidance | Evidence Type | α | β | Confidence | Status |
|---|---|---|---|---|---|---|---|
| 0 | — | — | — | 1.0 | 1.0 | 0.500 | CANDIDATE |
| 1 | UNSAFE | No | SUPPORTING | 2.0 | 1.0 | 0.667 | CANDIDATE |
| 2 | UNSAFE | No | SUPPORTING | 3.0 | 1.0 | 0.750 | CANDIDATE |
| 3 | UNSAFE | No | SUPPORTING | 4.0 | 1.0 | 0.800 | ACTIVE |
| 4 | SAFE | Yes | SUPPORTING | 5.0 | 1.0 | 0.833 | ACTIVE |
| 5 | SAFE | Yes | SUPPORTING | 6.0 | 1.0 | 0.857 | ACTIVE |

**Rule is failing (suspended):**

| Step | Classification | Guidance | Evidence Type | α | β | Confidence | Status |
|---|---|---|---|---|---|---|---|
| 0 | — | — | — | 1.0 | 1.0 | 0.500 | CANDIDATE |
| 1 | UNSAFE | No | SUPPORTING | 2.0 | 1.0 | 0.667 | CANDIDATE |
| 2 | UNSAFE | No | SUPPORTING | 3.0 | 1.0 | 0.750 | CANDIDATE |
| 3 | UNSAFE | No | SUPPORTING | 4.0 | 1.0 | 0.800 | ACTIVE |
| 4 | UNSAFE | Yes | CONTRADICTING | 4.0 | 2.0 | 0.667 | ACTIVE |
| 5 | UNSAFE | Yes | CONTRADICTING | 4.0 | 3.0 | 0.571 | ACTIVE |
| 6 | UNSAFE | Yes | CONTRADICTING | 4.0 | 4.0 | 0.500 | ACTIVE |
| 7 | UNSAFE | Yes | CONTRADICTING | 4.0 | 5.0 | 0.444 | ACTIVE |
| 8 | UNSAFE | Yes | CONTRADICTING | 4.0 | 6.0 | 0.400 | ACTIVE |
| 9 | UNSAFE | Yes | CONTRADICTING | 4.0 | 7.0 | 0.364 | SUSPENDED |

**Rule is archived:**

| Step | Evidence Type | α | β | Confidence | Status |
|---|---|---|---|---|---|
| 0 | — | 1.0 | 1.0 | 0.500 | CANDIDATE |
| 1 | SUPPORTING | 2.0 | 1.0 | 0.667 | CANDIDATE |
| 2 | SUPPORTING | 3.0 | 1.0 | 0.750 | CANDIDATE |
| 3 | SUPPORTING | 4.0 | 1.0 | 0.800 | ACTIVE |
| 4 | CONTRADICTING | 4.0 | 2.0 | 0.667 | ACTIVE |
| 5 | CONTRADICTING | 4.0 | 3.0 | 0.571 | ACTIVE |
| ... | CONTRADICTING | ... | ... | ... | ... |
| 10 | CONTRADICTING | 4.0 | 8.0 | 0.333 | SUSPENDED |
| 11 | CONTRADICTING | 4.0 | 9.0 | 0.308 | SUSPENDED → ARCHIVED |

### 6.4 Threshold Values

| Parameter | Default | Purpose |
|---|---|---|
| `promotion_threshold` | 0.75 | Confidence must be ≥ 0.75 for CANDIDATE→ACTIVE or SUSPENDED→ACTIVE |
| `demotion_threshold` | 0.35 | Confidence must be < 0.35 for ACTIVE→SUSPENDED |
| `min_evidence` | 3 | At least 3 non-baseline, non-neutral evidence required for promotion |

**Asymmetry rationale:** The promotion threshold (0.75) is higher than the symmetric midpoint (0.50) to ensure strong evidence before promoting. The demotion threshold (0.35) is asymmetric — lower than the promotion threshold — to create hysteresis. A rule needs more contradictory evidence to be demoted than it needed supporting evidence to be promoted. This prevents oscillation.

---

## 7. API Contracts

### 7.1 `GET /api/health`

**Request:** None

**Response (200):**
```json
{
    "status": "ok",
    "version": "0.1.0",
    "service": "evomind-observability"
}
```

**Response model:** `HealthResponse` (Pydantic)

### 7.2 `POST /api/query`

**Request:**
```json
{
    "prompt": "show me users",
    "mask_sql": false
}
```

**Validation:**
- `prompt`: required, string, min_length=1
- `mask_sql`: optional, boolean, defaults to false

**Response (200):**
```json
{
    "request_id": "uuid-string",
    "sql": "SELECT * FROM users WHERE id = 123",
    "classification": "unsafe",
    "rule_retrieved": false,
    "rule_name": null,
    "guidance_injected": false,
    "confidence": 0.667,
    "mask_sql": false,
    "evidence_type": null,
    "rule_status": "candidate"
}
```

**Response model:** `QueryResponse` (Pydantic)

**Error responses:**

| Condition | Status | Body |
|---|---|---|
| Empty/missing prompt | 422 | `{"detail": [{"loc": ["body", "prompt"], "msg": "field required"}]}` |
| Invalid mask_sql type | 422 | `{"detail": [{"loc": ["body", "mask_sql"], "msg": "value is not a valid boolean"}]}` |
| Internal error | 500 | `{"detail": "error message"}` |

---

## 8. Telemetry Specification

### 8.1 Span Names and Hierarchy

```
evomind.request                                           [ROOT]
├── evomind.rule.retrieval                               [CHILD]
├── evomind.guidance.injection                           [CHILD]  (conditional: only if rule retrieved)
├── evomind.sql.generation                               [CHILD]
├── evomind.sql.evaluation                               [CHILD]
├── evomind.observation.created                           [CHILD]
├── evomind.evidence.appended                            [CHILD]
├── evomind.confidence.updated                           [CHILD]
├── evomind.rule.state_change                            [CHILD]  (conditional: only if status changes)
└── evomind.lifecycle.complete                           [CHILD]

Startup trace (emitted once at application start):
evomind.system.startup                                   [ROOT]
└── evomind.rule.created                                 [CHILD]
```

### 8.2 Span Attributes

**Root span (`evomind.request`):**
- `app.version`: `"0.1.0"`
- `schema.version`: `"1.1.0"`
- `rule.version`: `"1.0.0"`
- `telemetry.version`: `"1.1.0"`
- `sql.hash`: SHA-256 hex string (only if `mask_sql=True`)
- `sql.truncated`: truncated SQL string (only if `mask_sql=True`)

**Complete span (`evomind.lifecycle.complete`):**
- `app.request.prompt`: The user prompt
- `app.request.sql`: The generated SQL
- `app.request.safety`: Classification value
- `app.request.rule_retrieved`: Boolean string
- `app.request.confidence`: Float string
- `app.request.evidence_type`: Evidence type value
- `app.request.rule_status`: Rule status value
- `app.request.mask_sql`: Boolean string

### 8.3 Metric Instruments

**`evomind.requests.total`** (Counter)
- Type: Counter (monotonic, integer)
- Unit: 1 (requests)
- Description: "Total number of query requests"
- Attributes: `classification`, `rule_retrieved`, `guidance_injected`
- Emission point: `POST /api/query` handler

**`evomind.sql.safety.ratio`** (ObservableGauge)
- Type: ObservableGauge (non-monotonic, float)
- Unit: 1 (ratio)
- Description: "Ratio of safe SQL classifications"
- Attributes: `rule_id`
- Callback: Reads `COUNT(*) FROM observations WHERE classification='safe'` / `COUNT(*) FROM observations`
- Collection: At meter collection interval (default 5s)

**`evomind.rule.confidence`** (ObservableGauge)
- Type: ObservableGauge (non-monotonic, float)
- Unit: 1 (confidence value)
- Description: "Current confidence for each rule"
- Attributes: `rule_id`
- Callback: Reads `SELECT confidence FROM behavioral_rules`
- Collection: At meter collection interval

**`evomind.rule.evidence.count`** (ObservableGauge)
- Type: ObservableGauge (non-monotonic, integer)
- Unit: 1 (count)
- Description: "Evidence count per rule and type"
- Attributes: `rule_id`, `evidence_type` (supporting/contradicting/total)
- Callback: Reads `SELECT supporting_count, contradicting_count FROM behavioral_rules`
- Collection: At meter collection interval

### 8.4 Resource Attributes

All spans and metrics carry these resource attributes:

| Attribute | Value |
|---|---|
| `service.name` | `evomind-observability` |
| `service.version` | `0.1.0` |
| `schema.version` | `1.1.0` |
| `rule.version` | `1.0.0` |
| `telemetry.version` | `1.1.0` |
| `telemetry.distro.name` | `evomind-observability` |

### 8.5 Exception Recording

When any step in the pipeline raises an exception:

1. The root span is set to `StatusCode.ERROR`
2. `span.record_exception(error)` is called with exception attributes
3. The `complete` span records the error and re-raises
4. The API layer returns a 500 response

---

## 9. Database Schema

### 9.1 Table Definitions

```sql
-- Table: behavioral_rules
-- Stores rule definitions and current state
CREATE TABLE IF NOT EXISTS behavioral_rules (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    guidance_text TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('candidate','active','suspended','archived')),
    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
    alpha REAL NOT NULL CHECK(alpha > 0),
    beta REAL NOT NULL CHECK(beta > 0),
    promotion_threshold REAL NOT NULL DEFAULT 0.75,
    demotion_threshold REAL NOT NULL DEFAULT 0.35,
    min_evidence INTEGER NOT NULL DEFAULT 3,
    supporting_count INTEGER NOT NULL DEFAULT 0,
    contradicting_count INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Table: request_contexts
-- Stores per-request metadata
CREATE TABLE IF NOT EXISTS request_contexts (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    sql_generated TEXT NOT NULL,
    guidance_injected INTEGER NOT NULL DEFAULT 0,
    rule_retrieved_id TEXT,
    rule_retrieved INTEGER NOT NULL DEFAULT 0,
    classification TEXT NOT NULL,
    trace_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (rule_retrieved_id) REFERENCES behavioral_rules(id)
);

-- Table: observations
-- Stores evaluation outcomes per request
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    classification TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    sql_generated TEXT NOT NULL,
    evaluation_reason TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (request_id) REFERENCES request_contexts(id),
    FOREIGN KEY (rule_id) REFERENCES behavioral_rules(id)
);

-- Table: evidence_records
-- Stores confidence before/after/delta per evidence event
CREATE TABLE IF NOT EXISTS evidence_records (
    id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    request_id TEXT NOT NULL,
    confidence_before REAL NOT NULL,
    confidence_after REAL NOT NULL,
    delta REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (observation_id) REFERENCES observations(id),
    FOREIGN KEY (rule_id) REFERENCES behavioral_rules(id),
    FOREIGN KEY (request_id) REFERENCES request_contexts(id)
);

-- Table: learning_states
-- Point-in-time snapshots after each evidence update
CREATE TABLE IF NOT EXISTS learning_states (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    supporting_count INTEGER NOT NULL DEFAULT 0,
    contradicting_count INTEGER NOT NULL DEFAULT 0,
    total_evidence INTEGER NOT NULL DEFAULT 0,
    snapshot_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (request_id) REFERENCES request_contexts(id),
    FOREIGN KEY (rule_id) REFERENCES behavioral_rules(id)
);
```

### 9.2 Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_observations_request ON observations(request_id);
CREATE INDEX IF NOT EXISTS idx_observations_rule ON observations(rule_id);
CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_request ON evidence_records(request_id);
CREATE INDEX IF NOT EXISTS idx_evidence_rule ON evidence_records(rule_id);
CREATE INDEX IF NOT EXISTS idx_learning_state_rule ON learning_states(rule_id);
```

### 9.3 Seed Data

```sql
INSERT OR IGNORE INTO behavioral_rules (
    id, name, guidance_text, status, confidence, alpha, beta,
    promotion_threshold, demotion_threshold, min_evidence,
    supporting_count, contradicting_count, version
) VALUES (
    '<generated-uuid>',
    'use parameterized queries',
    'When generating SQL, always use parameterized queries with ? placeholders...',
    'candidate', 0.5, 1.0, 1.0,
    0.75, 0.35, 3,
    0, 0, 1
);
```

### 9.4 Common Queries

```sql
-- Current rule state
SELECT name, status, confidence, alpha, beta, supporting_count, contradicting_count
FROM behavioral_rules;

-- Confidence history
SELECT snapshot_at, confidence, status
FROM learning_states
WHERE rule_id = '<id>'
ORDER BY snapshot_at;

-- All evidence for a rule with deltas
SELECT e.id, o.classification, e.evidence_type, e.confidence_before, e.confidence_after, e.delta
FROM evidence_records e
JOIN observations o ON e.observation_id = o.id
WHERE e.rule_id = '<id>'
ORDER BY e.created_at;

-- Requests with unsafe classification
SELECT rc.id, rc.prompt, rc.sql_generated, rc.classification, rc.guidance_injected
FROM request_contexts rc
WHERE rc.classification = 'unsafe';

-- Orphan observations (no evidence record)
SELECT o.id, o.request_id, o.created_at
FROM observations o
LEFT JOIN evidence_records e ON o.id = e.observation_id
WHERE e.id IS NULL;

-- Safety ratio over time
SELECT
    strftime('%Y-%m-%d %H', created_at) as hour,
    COUNT(*) as total,
    SUM(CASE WHEN classification = 'safe' THEN 1 ELSE 0 END) as safe_count
FROM observations
GROUP BY hour
ORDER BY hour;
```

---

## 10. Infrastructure Architecture

### 10.1 Docker Compose Topology

**Network:** `evomind_default` (bridge, default)

**Volumes:**
- `clickhouse-storage`: ClickHouse data (persists across restarts)
- `clickhouse-logs`: ClickHouse logs

**Service Dependencies:**
```
clickhouse ← query-service ← frontend
                              ↓
                   otel-collector ← evomind
```

### 10.2 Service Specifications

| Service | Image | Ports | Depends On |
|---|---|---|---|
| clickhouse | clickhouse:24.3-alpine | 9000, 8123 | — |
| query-service | signoz/query-service:0.76.2 | 8080 | clickhouse (healthy) |
| frontend | signoz/frontend:0.76.0-a13d1c89 | 3301 | query-service (healthy) |
| signoz-otel-collector | signoz/signoz-otel-contrib:v0.144.6 | 4317, 4318 | query-service |
| evomind | (build: ./Dockerfile) | 8000 | signoz-otel-collector |

### 10.3 OTel Collector Pipeline

```
Receiver: OTLP gRPC (0.0.0.0:4317)
    │
Processor: Batch (timeout=1s, send_batch_size=100)
    │
Exporter: ClickHouse (tcp://clickhouse:9000, database=signoz_traces)
```

Both traces and metrics use the same pipeline.

### 10.4 SigNoz Dashboard Panels

1. **Request Rate** — Time series of `evomind.requests.total` counter
2. **SQL Safety Ratio** — Time series of `evomind.sql.safety.ratio` gauge
3. **Confidence Over Time** — Line chart of `evomind.rule.confidence` per rule
4. **Evidence Timeline** — Bar chart of `evomind.rule.evidence.count` by type
5. **State Transitions** — Step chart from `learning_states` status column
6. **Rule Lifecycle** — Gantt-like view of rule status duration
7. **Trace Explorer** — Raw trace list with duration + status
8. **Classification Breakdown** — Pie chart of safe/unsafe/ambiguous
9. **Confidence Delta Distribution** — Histogram of `evidence_records.delta`
10. **Performance Timeline** — P50/P95/P99 latency of `evomind.request`

### 10.5 Dockerfile

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY evomind/ ./evomind/
COPY demo.py .
EXPOSE 8000
CMD ["python", "demo.py", "--auto"]
```

Single-stage build. No distroless. Image size approximately 150MB.

---

## 11. Testing Architecture

### 11.1 Test Hierarchy

```
tests/
├── conftest.py              # Shared fixtures
├── acceptance/              # End-to-end behavioral tests
│   ├── test_api.py          # HTTP endpoint tests
│   └── test_lifecycle.py    # Startup/shutdown tests
├── integration/             # Multi-component tests
│   ├── test_orchestrator.py # Full pipeline
│   ├── test_learning_loop.py# State machine transitions
│   ├── test_repositories.py # CRUD operations
│   ├── test_sql_agent.py    # Agent mode matrix
│   └── test_telemetry.py    # Telemetry integration
├── unit/                    # Single-component tests
│   ├── test_config.py, test_confidence_engine.py, test_database.py,
│   ├── test_enums.py, test_evaluator.py, test_evidence_store.py,
│   ├── test_exceptions.py, test_guidance_injector.py,
│   ├── test_metrics_registry.py, test_models.py,
│   ├── test_observation_factory.py, test_rule_retriever.py,
│   └── test_span_helper.py
└── __init__.py
```

### 11.2 Test Database Fixture

All tests use an in-memory SQLite database:

```python
@pytest.fixture
def db():
    database = Database()
    database.initialize(":memory:")
    Schema.create_tables(database.connection)
    Seed.seed(database.connection)
    yield database
    database.close()
```

### 11.3 Coverage Requirements

- **Required:** ≥ 90% line coverage on production code
- **Current:** 92% (106 uncovered lines out of 1314)
- **Exempt from coverage:** `__init__.py` files, `__main__.py`

### 11.4 Failure Injection Tests

File: `ops/_validate_failure.py`

| Test | Scenario | Expected Behavior |
|---|---|---|
| 1 | Empty prompt `""` | 422 response |
| 2 | Missing `prompt` field | 422 response |
| 3 | Whitespace-only prompt `"   "` | 422 response |
| 4 | `prompt: null` | 422 response |
| 5 | OTEL endpoint unreachable | Request succeeds, spans dropped silently |
| 6 | 100 sequential requests | All succeed, total < 5s |
| 7 | Two independent app instances | Each maintains independent state |
| 8 | 10K character prompt | Handled without error |
| 9 | Settings from environment | Values reflect env vars |

---

## 12. Learning Lifecycle Walkthrough

### 12.1 Phase 1: Initial State (0 Evidence)

- Rule status: CANDIDATE
- Confidence: 0.500
- α: 1.0, β: 1.0
- Guidance is NOT injected (rule not active)

**Request:** `"show me users"`

1. `RuleRetriever.retrieve()` → empty list (no active rules)
2. `GuidanceInjector`: NOT called
3. `SQLAgent.generate("show me users")` → `"SELECT * FROM users WHERE id = 123"` (UNSAFE, no guidance)
4. `SqlSafetyEvaluator.evaluate(sql)` → UNSAFE (inline literal `123`)
5. `ObservationFactory.create(UNSAFE, guidance_injected=False)` → evidence_type = SUPPORTING
6. `ConfidenceEngine.update(SUPPORTING)` → α=2.0, β=1.0, confidence=0.667
7. State transition check: confidence 0.667 < 0.75 → stay CANDIDATE

**After request:**
- supporting_count: 1, contradicting_count: 0
- Confidence: 0.667
- Status: CANDIDATE

### 12.2 Phase 2: Evidence Accumulation

**Request 2:** `"show me users"`
- Same flow as above
- α=3.0, β=1.0, confidence=0.750
- State transition: 0.750 >= 0.75 AND evidence 2 < 3 → stay CANDIDATE

**Request 3:** `"show me users"`
- α=4.0, β=1.0, confidence=0.800
- State transition: 0.800 >= 0.75 AND evidence 3 >= 3 → **PROMOTE TO ACTIVE**

**After 3 requests:**
- supporting_count: 3, contradicting_count: 0
- Confidence: 0.800
- Status: ACTIVE
- Guidance will be injected on future requests

### 12.3 Phase 3: Active with Guidance

**Request 4:** `"show me users"`

1. `RuleRetriever.retrieve()` → [active rule]
2. `GuidanceInjector.inject("show me users", rule)` → `guidance...\n---\nUser Query: show me users`
3. `SQLAgent.generate(prompt_with_guidance, guidance)` → `"SELECT * FROM users WHERE id = ?"` (SAFE, with guidance)
4. `SqlSafetyEvaluator.evaluate(sql)` → SAFE (parameterized query)
5. `ObservationFactory.create(SAFE, guidance_injected=True)` → evidence_type = SUPPORTING
6. `ConfidenceEngine.update(SUPPORTING)` → α=5.0, β=1.0, confidence=0.833
7. State transition check: stay ACTIVE

**After request 4:**
- supporting_count: 4, contradicting_count: 0
- Confidence: 0.833
- Status: ACTIVE

### 12.4 Phase 4: Rule Failure (Contradiction)

**Request 5:** `"drop table users"`

1. Rule is active, guidance injected
2. Agent with guidance → still produces DANGEROUS DDL (agent does not understand DDL warnings in guidance)
3. `SqlSafetyEvaluator.evaluate(sql)` → UNSAFE (DDL detected)
4. `ObservationFactory.create(UNSAFE, guidance_injected=True)` → evidence_type = CONTRADICTING
5. `ConfidenceEngine.update(CONTRADICTING)` → α=5.0, β=2.0, confidence=0.714
6. State transition: confidence 0.714 >= 0.35 → stay ACTIVE

**Repeated contradictions (5 more):**
- After each: α stays at 5.0, β increments by 1
- Confidence trajectory: 0.667 → 0.625 → 0.588 → 0.556 → 0.526 → 0.500
- At β=7.0, confidence=0.417: still above 0.35 → stay ACTIVE

### 12.5 Phase 5: Suspension

**Request 11:** `"drop table users"` (5th contradiction, β=6.0)
- α=5.0, β=6.0, confidence=0.455 → stay ACTIVE

**Request 12:** `"drop table users"` (6th contradiction, β=7.0)
- α=5.0, β=7.0, confidence=0.417 → stay ACTIVE

**Request 13:** `"drop table users"` (7th contradiction, β=8.0)
- α=5.0, β=8.0, confidence=0.385 → stay ACTIVE

**Request 14:** `"drop table users"` (8th contradiction, β=9.0)
- α=5.0, β=9.0, confidence=0.357 → **0.357 < 0.35 → SUSPEND**

**After request 14:**
- supporting_count: 4, contradicting_count: 9 (or whatever the count is)
- Confidence: 0.357
- Status: SUSPENDED
- No longer retrieved on future requests

### 12.6 Phase 6: Re-promotion or Archive

**Re-promotion scenario:** If after suspension the agent consistently produces unsafe SQL (without guidance), the evidence will be SUPPORTING (rule is needed), confidence goes up, and at >= 0.75 the rule is re-promoted to ACTIVE.

**Archive scenario:** If after suspension the next contradiction arrives (evidence_type=CONTRADICTING), AND contradicting_count > supporting_count, the rule transitions to ARCHIVED.

---

## 13. Configuration Reference

### 13.1 Settings Fields

All prefixed with `EVOMIND_` when set via environment variable.

| Field | Type | Default | Description |
|---|---|---|---|
| `host` | str | `"0.0.0.0"` | Server bind address |
| `port` | int | `8000` | Server port |
| `reload` | bool | `False` | Hot reload for development |
| `db_path` | str | `"evomind.db"` | SQLite database path |
| `otel_endpoint` | str | `"http://localhost:4317"` | OTLP gRPC endpoint |
| `service_name` | str | `"evomind-observability"` | OTel service name |
| `service_version` | str | `"0.1.0"` | OTel service version |
| `schema_version` | str | `"1.1.0"` | Database schema version |
| `rule_version` | str | `"1.0.0"` | Rule definition version |
| `telemetry_version` | str | `"1.1.0"` | Telemetry layer version |
| `promotion_threshold` | float | `0.75` | CANDIDATE→ACTIVE threshold |
| `demotion_threshold` | float | `0.35` | ACTIVE→SUSPENDED threshold |
| `min_evidence_for_promotion` | int | `3` | Min evidence for promotion |
| `default_alpha` | float | `1.0` | Beta prior α |
| `default_beta` | float | `1.0` | Beta prior β |
| `mask_sql` | bool | `False` | Enable SQL masking in telemetry |
| `sql_truncation_length` | int | `200` | Truncation length for masked SQL |
| `seed_default_rule` | bool | `True` | Auto-seed default rule on startup |

### 13.2 Environment Variable Examples

```bash
# Change database location
export EVOMIND_DB_PATH=/data/evomind.db

# Point to Docker service
export EVOMIND_OTEL_ENDPOINT=http://signoz-otel-collector:4317

# Enable SQL masking
export EVOMIND_MASK_SQL=true
export EVOMIND_SQL_TRUNCATION_LENGTH=100

# Override thresholds
export EVOMIND_PROMOTION_THRESHOLD=0.80
export EVOMIND_DEMOTION_THRESHOLD=0.30
```

---

## 14. Exception Reference

### 14.1 Exception Hierarchy

```
EvoMindError (Exception)
├── ConfigurationError
│   └── Raised when: Invalid settings, missing required env vars, type mismatch
├── DatabaseError
│   └── Raised when: SQLite connection fails, query execution error, schema creation failure
├── AgentError
│   └── Raised when: SQL agent generates invalid output, pattern matching fails
├── EvaluationError
│   └── Raised when: Evaluator fails to parse SQL, sqlparse library error
├── EvidenceStoreError
│   └── Raised when: Rule not found during evidence append, persistence failure
├── RuleRetrievalError
│   └── Raised when: Repository query fails, active rules not retrievable
├── GuidanceInjectionError
│   └── Raised when: Prompt formatting fails, guidance text template error
├── ServiceRegistrationError
│   └── Raised when: Duplicate service key registered, service key not found on resolve
├── OrchestrationError
│   └── Raised when: Pipeline execution fails, invalid input, any unhandled exception in pipeline
└── TelemetryError
    └── Raised when: TracerProvider initialization fails, exporter connection error
```

### 14.2 Error Flow

```
Orchestrator.process_request()
    │
    ├── EvoMindError subclass raised → propagate as-is
    │
    ├── Generic Exception → wrap in OrchestrationError, attach original as __cause__
    │
    └── No exception → return RequestContext

API endpoint (POST /api/query)
    │
    ├── EvoMindError / Exception → HTTP 500 with str(error)
    │
    └── No exception → HTTP 200 with QueryResponse
```

### 14.3 Testing Exception Coverage

Test creates each exception type:
```python
exc = ConfigurationError("test message")
assert isinstance(exc, EvoMindError)
assert isinstance(exc, Exception)
assert str(exc) == "test message"
```

---

## 15. Glossary

| Term | Definition |
|---|---|
| **Alpha (α)** | Beta distribution parameter for supporting evidence. Starts at 1.0. |
| **Baseline evidence** | Pre-promotion safe classification. Provides no signal about rule effectiveness. |
| **Behavioral rule** | A rule defining desired/undesired agent behavior, with guidance text and confidence tracking. |
| **Beta (β)** | Beta distribution parameter for contradicting evidence. Starts at 1.0. |
| **Classification** | Output of the SQL safety evaluator: safe, unsafe, or ambiguous. |
| **Confidence** | Posterior mean of the Beta distribution: α/(α+β). Range [0, 1]. |
| **Contradicting evidence** | Post-promotion unsafe classification. Indicates the rule failed. |
| **Evidence** | An observation linked to a rule. Can be supporting, contradicting, baseline, or neutral. |
| **Evidence delta** | `confidence_after - confidence_before` for a single evidence event. |
| **Evidence record** | A persisted link between an observation and a rule, with before/after confidence values. |
| **Guidance** | Text prepended to a user prompt, instructing the agent on desired behavior. |
| **Guidance injection** | The process of prepending rule guidance to a user prompt before sending to the agent. |
| **Hysteresis** | The gap between promotion (0.75) and demotion (0.35) thresholds, preventing state oscillation. |
| **Learning state** | A point-in-time snapshot of a rule's confidence, status, and evidence counts. |
| **Masked SQL** | Truncated and SHA-256-hashed SQL for privacy-preserving telemetry. |
| **Neutral evidence** | Ambiguous classification. Provides no signal about rule effectiveness. |
| **Observation** | The outcome of a single evaluation, including classification, evidence type, and generated SQL. |
| **OTel** | OpenTelemetry — the vendor-neutral observability framework used for traces and metrics. |
| **OTLP** | OpenTelemetry Protocol — the gRPC-based protocol for exporting telemetry data. |
| **Post-promotion** | State after a rule becomes ACTIVE. Guidance is injected into prompts. |
| **Pre-promotion** | State before a rule becomes ACTIVE. Guidance is NOT injected. |
| **Promotion threshold** | The confidence level (default 0.75) required to promote a rule from CANDIDATE to ACTIVE. |
| **Request context** | A persisted record of a single request, containing prompt, SQL, classification, and trace ID. |
| **SigNoz** | The open-source observability backend (ClickHouse + query service + UI). |
| **Supporting evidence** | Evidence that the rule is needed (pre-promotion unsafe) or works (post-promotion safe). |
| **Three-state evidence** | The model distinguishing pre-promotion (unsafe→supporting, safe→baseline) from post-promotion (safe→supporting, unsafe→contradicting). |
| **Trace** | A collection of spans representing a single request lifecycle. |
| **WAL mode** | SQLite Write-Ahead Log — allows concurrent reads during writes. |
| **Write-only telemetry** | Design principle: SigNoz never participates in the learning loop. Telemetry is best-effort. |

---

*End of Architecture Book. This document is a permanent reference and should be updated whenever the architecture changes.*
