# Deliverable 2: Technical Handover Document

**Project:** EvoMind Observability  
**Author:**  
**Audience:** CTO, Principal Engineer, Distributed Systems Engineer, Observability Engineer  
**Status:** Final — Repository Frozen for Hackathon Submission

---

## Table of Contents

1. [Project Overview and Philosophy](#1-project-overview-and-philosophy)
2. [Directory Structure and File Inventory](#2-directory-structure-and-file-inventory)
3. [Package-by-Package Deep Dive](#3-package-by-package-deep-dive)
   - 3.1 `evomind/__init__.py` and `__main__.py`
   - 3.2 `evomind/app.py`
   - 3.3 `evomind/config/`
   - 3.4 `evomind/exceptions/`
   - 3.5 `evomind/interfaces/`
   - 3.6 `evomind/models/`
   - 3.7 `evomind/agent/`
   - 3.8 `evomind/evaluator/`
   - 3.9 `evomind/observation/`
   - 3.10 `evomind/learning/`
   - 3.11 `evomind/orchestration/`
   - 3.12 `evomind/persistence/`
   - 3.13 `evomind/telemetry/`
   - 3.14 `evomind/api/`
4. [Test Suite Analysis](#4-test-suite-analysis)
5. [Infrastructure and Deployment](#5-infrastructure-and-deployment)
6. [Architecture Decisions (ADRs)](#6-architecture-decisions-adrs)
7. [Common Pitfalls and Gotchas](#7-common-pitfalls-and-gotchas)
8. [Operational Runbook](#8-operational-runbook)

---

## 1. Project Overview and Philosophy

EvoMind Observability makes the behavioral learning lifecycle of an AI agent observable. The project implements one complete vertical slice — one agent, one domain, one behavioral rule, one learning lifecycle, one observability pipeline — to prove the thesis: "The behavioral learning lifecycle of an AI agent can be represented as an observable production system."

**Key design principles:**

1. **Frozen architecture**: All interfaces, data models, and workflows are final. No new features are permitted after Phase 5.
2. **Write-only telemetry**: OpenTelemetry is a unidirectional pipeline. SigNoz never participates in the learning loop. If SigNoz is unreachable, the application continues without error.
3. **Pluggable components**: Every major component is defined by an abstract interface in `evomind/interfaces/`. The mock SQL agent can be replaced with a real LLM without changing any other component.
4. **Determinism where possible**: The SQL agent is keyword-mapped (no LLM), the SQL evaluator uses sqlparse AST analysis (no LLM), and the confidence engine is a closed-form Beta-Bernoulli update. Non-determinism is confined to the agent interface.
5. **Trace everything**: Every lifecycle step emits a named OpenTelemetry span. The trace hierarchy is intentionally flat (siblings under a root span) for flamegraph readability.

---

## 2. Directory Structure and File Inventory

```
evomind-observability/
├── evomind/
│   ├── __init__.py                    # Version string
│   ├── __main__.py                    # CLI entry: uvicorn evomind.app:app
│   ├── app.py                         # FastAPI factory function
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py                  # GET /health, POST /query
│   ├── agent/
│   │   ├── __init__.py
│   │   └── deterministic_agent.py     # Mock SQL agent
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                # Pydantic Settings (19 fields)
│   ├── evaluator/
│   │   ├── __init__.py
│   │   └── sql_safety_evaluator.py    # 12-rule SQL safety classifier
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── errors.py                  # 10 typed exceptions
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── agent.py                   # SQLAgent ABC
│   │   ├── confidence.py              # ConfidenceEngine ABC
│   │   ├── evaluator.py               # OutcomeEvaluator ABC
│   │   ├── evidence.py                # EvidenceStore ABC
│   │   ├── guidance.py                # GuidanceInjector ABC
│   │   ├── observation.py             # ObservationFactory ABC
│   │   └── rules.py                   # RuleRetriever ABC
│   ├── learning/
│   │   ├── __init__.py
│   │   ├── confidence_engine.py       # Beta-Bernoulli update + state machine
│   │   ├── evidence_store.py          # Persist observations
│   │   ├── guidance_injector.py       # Prepend guidance text
│   │   └── rule_retriever.py          # Query active rules
│   ├── models/
│   │   ├── __init__.py
│   │   ├── behavioral_rule.py         # Rule entity with alpha/beta/state
│   │   ├── enums.py                   # RuleStatus, EvidenceType, Classification
│   │   ├── evaluation_result.py       # Transient evaluator output
│   │   ├── evidence_record.py         # Persisted link: observation→rule
│   │   ├── learning_state.py          # Point-in-time snapshot
│   │   ├── observation.py             # Single evaluation outcome
│   │   └── request_context.py         # Full request lifecycle data
│   ├── observation/
│   │   ├── __init__.py
│   │   └── observation_factory.py     # Evidence type derivation
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── lifecycle.py               # Startup: telemetry→DB→services
│   │   ├── orchestrator.py            # 11-step request pipeline
│   │   └── service_registry.py        # DI container
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── database.py                # SQLite wrapper (WAL, FK, thread-local)
│   │   ├── schema.py                  # 5 tables, 6 indexes
│   │   ├── seed.py                    # Default behavioral rule
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # Generic CRUD base class
│   │   │   ├── behavioral_rule_repo.py
│   │   │   ├── evidence_record_repo.py
│   │   │   ├── learning_state_repo.py
│   │   │   ├── observation_repo.py
│   │   │   └── request_context_repo.py
│   │   └── ...
│   └── telemetry/
│       ├── __init__.py
│       ├── exception_instrumentor.py  # Exception recording policy
│       ├── exporter_config.py          # OTLP gRPC exporter creation
│       ├── meter_manager.py            # MeterProvider lifecycle
│       ├── metrics_registry.py         # 4 instruments
│       ├── span_helper.py              # Consistent span tooling
│       └── tracer_manager.py           # TracerProvider lifecycle
├── tests/
│   ├── conftest.py                     # Shared SQLite in-memory fixture
│   ├── acceptance/
│   │   ├── test_api.py                 # API endpoint integration
│   │   └── test_lifecycle.py           # Startup/shutdown
│   ├── integration/
│   │   ├── test_orchestrator.py        # Full pipeline validation
│   │   ├── test_learning_loop.py       # State machine transitions
│   │   ├── test_repositories.py        # CRUD operations
│   │   ├── test_sql_agent.py           # Safe/unsafe mode matrix
│   │   └── test_telemetry.py           # Telemetry integration
│   ├── unit/
│   │   ├── test_config.py              # Settings loading and defaults
│   │   ├── test_confidence_engine.py   # Beta-Bernoulli and state machine
│   │   ├── test_database.py            # SQLite wrapper behavior
│   │   ├── test_enums.py               # Enum coverage
│   │   ├── test_evaluator.py           # 12 detection rules
│   │   ├── test_evidence_store.py      # Evidence persistence
│   │   ├── test_exceptions.py          # Exception hierarchy
│   │   ├── test_guidance_injector.py   # Guidance prepending
│   │   ├── test_metrics_registry.py    # Instrument creation
│   │   ├── test_models.py              # Dataclass behavior
│   │   ├── test_observation_factory.py # Three-state evidence semantics
│   │   ├── test_rule_retriever.py      # Active rule filtering
│   │   └── test_span_helper.py         # Span attribute formatting
│   └── __init__.py
├── ops/
│   ├── otel-collector-config.yaml      # OTel collector pipeline
│   ├── signoz-dashboard.json            # 10-panel SigNoz dashboard
│   └── _validate_failure.py            # 9 failure injection scenarios
├── docs/
│   ├── executive_summary.md
│   ├── architecture_overview.md
│   ├── data_model.md
│   ├── state_machines.md
│   ├── confidence_model.md
│   ├── sql_evaluator_detailed.md
│   ├── telemetry_model.md
│   ├── api_contracts.md
│   ├── testing_strategy.md
│   ├── demo_plan.md
│   ├── architecture_decisions.md
│   ├── DELIVERABLE_1_PROFESSOR_EMAIL.md
│   ├── DELIVERABLE_2_TECHNICAL_HANDOVER.md
│   └── DELIVERABLE_3_ARCHITECTURE_BOOK.md
├── demo.py                              # 366-line automated CLI demo
├── docker-compose.yml                   # 5 services, pinned versions
├── Dockerfile                           # Multi-stage Python 3.10-slim
├── pyproject.toml                       # Dependencies and project metadata
├── LICENSE                              # MIT
├── .gitignore
├── README.md
├── DEMO.md
├── JUDGE_GUIDE.md
├── OBSERVABILITY_GUIDE.md
├── TRACE_WALKTHROUGH.md
├── HACKATHON_SUBMISSION_AUDIT.md
└── RELEASE_VALIDATION_REPORT.md
```

Total production files: 21 Python files  
Total test files: 19 Python files  
Total architecture docs: 11 (plus 3 handover deliverables = 14)  
Total top-level docs: 7

---

## 3. Package-by-Package Deep Dive

### 3.1 `evomind/__init__.py` and `__main__.py`

**`evomind/__init__.py`:**

```python
__version__ = "0.1.0"
```

A single-export init file. The version string is consumed by:
- `app.py`: sets `app.version` for the health endpoint
- `TracerManager`: sets `telemetry.distro.version` resource attribute
- `SpanHelper`: sets `app.version` attribute on all spans

**`evomind/__main__.py`:**

```python
import uvicorn
from evomind.config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "evomind.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
```

Entry point for `python -m evomind`. Reads host/port/reload from settings. The `reload` flag is set but not recommended in Docker (use `python demo.py` instead).

---

### 3.2 `evomind/app.py`

```python
from fastapi import FastAPI
from evomind.api.routes import router
from evomind.orchestration.lifecycle import LifecycleManager

def create_app() -> FastAPI:
    app = FastAPI(title="EvoMind Observability", version="0.1.0")
    lifecycle_manager = LifecycleManager()

    @app.on_event("startup")
    async def startup():
        lifecycle_manager.startup()

    app.include_router(router)
    app.state.lifecycle_manager = lifecycle_manager

    @app.on_event("shutdown")
    async def shutdown():
        lifecycle_manager.shutdown()

    return app

app = create_app()
```

**Design notes:**

- `create_app()` is a factory function — tests can call it to create fresh instances. The module-level `app` is the global singleton used by uvicorn.
- `LifecycleManager` is synchronous (OTel SDK is synchronous). The async `startup`/`shutdown` event handlers wrap synchronous calls. This is safe because startup/shutdown are blocking operations.
- `app.state.lifecycle_manager` stores the manager for test introspection (`app.state.lifecycle_manager._db.connection`).
- FastAPI includes the router after construction, enabling route-level dependency injection.

**Lifecycle sequence:**

1. `LifecycleManager.startup()` called:
   - `TracerManager.initialize()` → `TracerProvider` with `BatchSpanProcessor` + `OTLPSpanExporter`
   - `MeterManager.initialize()` → `MeterProvider`
   - `MetricsRegistry.reset()` → create 4 instruments
   - `Database.initialize()` → open SQLite, set WAL mode, enable FK
   - `Schema.create_tables()` → run 5 CREATE TABLE + 6 CREATE INDEX statements
   - `Seed.seed()` → INSERT OR IGNORE default rule
   - `ServiceRegistry.register_all()` → register all 7 core services
   - Emit `evomind.system.startup` span
   - Emit `evomind.rule.created` span for seeded rule
2. `LifecycleManager.shutdown()` called:
   - `TracerManager.shutdown()` → flush and shutdown span processor
   - `MeterManager.shutdown()` → shutdown meter provider
   - `Database.close()` → close SQLite connection

**Consequence of the synchronous-wrapped-in-async pattern:** If startup throws, the ASGI server will catch the exception and log the traceback. The application will enter a degraded state where health checks fail. In Docker, the container will continue running but return 503 on health checks.

---

### 3.3 `evomind/config/settings.py`

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVOMIND_", frozen=True)

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    db_path: str = "evomind.db"
    otel_endpoint: str = "http://localhost:4317"
    service_name: str = "evomind-observability"
    service_version: str = "0.1.0"
    schema_version: str = "1.1.0"
    rule_version: str = "1.0.0"
    telemetry_version: str = "1.1.0"
    promotion_threshold: float = 0.75
    demotion_threshold: float = 0.35
    min_evidence_for_promotion: int = 3
    default_alpha: float = 1.0
    default_beta: float = 1.0
    mask_sql: bool = False
    sql_truncation_length: int = 200
    seed_default_rule: bool = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

**19 fields, all with defaults.** Environment variables are prefixed with `EVOMIND_` (e.g., `EVOMIND_DB_PATH=./data/evomind.db`). The config object is frozen after construction — no field can be mutated after creation.

**Notable defaults:**

| Field | Default | Rationale |
|---|---|---|
| `host` | `0.0.0.0` | Binds to all interfaces for Docker/network accessibility |
| `port` | 8000 | Standard local dev port; matches Docker EXPOSE |
| `db_path` | `evomind.db` | CWD-relative; Docker volume maps `/app/evomind.db` |
| `otel_endpoint` | `http://localhost:4317` | Default OTLP gRPC port; Docker network uses service name |
| `promotion_threshold` | 0.75 | Asymmetric with demotion (0.35) for hysteresis |
| `demotion_threshold` | 0.35 | Only tested for ACTIVE state; lower = sticky |
| `min_evidence_for_promotion` | 3 | Avoids single-observation promotion |
| `mask_sql` | False | Opt-in to reduce SQL cardinality in telemetry |
| `seed_default_rule` | True | Auto-seeds "use parameterized queries" at startup |

**The `lru_cache()` pattern** ensures that `get_settings()` returns the same frozen instance on every call. Tests must not mutate the returned settings. To change settings in tests, set environment variables before the first call to `get_settings()`.

---

### 3.4 `evomind/exceptions/errors.py`

Ten exception classes in a single-hierarchy tree:

```
EvoMindError (base)
├── ConfigurationError         # Invalid settings/environment
├── DatabaseError              # SQLite connection/query failure
├── AgentError                 # SQL agent failure
├── EvaluationError            # Evaluator failure
├── EvidenceStoreError         # Evidence storage failure
├── RuleRetrievalError         # Rule not found or query failure
├── GuidanceInjectionError     # Guidance prepend failure
├── ServiceRegistrationError   # DI container duplicate/missing
├── OrchestrationError         # Pipeline execution failure
└── TelemetryError             # OTel SDK initialization failure
```

Each exception:
- Extends `EvoMindError` (which extends `Exception`)
- Has only `__init__` (message) and `__str__`
- No additional attributes, no error codes
- Caught by the orchestrator and re-raised as `OrchestrationError`

**Testing coverage:** `test_exceptions.py` creates an instance of each and verifies `isinstance` hierarchy and string representation.

**Critical detail:** The orchestrator's `process_request` wraps the entire pipeline body in:

```python
try:
    # ... 11 steps ...
except EvoMindError:
    raise
except Exception as e:
    raise OrchestrationError(...) from e
```

This means `EvoMindError` subclasses propagate directly to the API layer. The API endpoint catches `Exception` generically (FastAPI default) and returns a 500 response. If you want to return specific HTTP status codes per exception type, add exception handlers to the FastAPI app.

---

### 3.5 `evomind/interfaces/`

Seven abstract base classes, each in its own file:

#### `SQLAgent` (`agent.py`)

```python
class SQLAgent(ABC):
    @abstractmethod
    def generate(self, prompt: str, guidance: str | None = None) -> str: ...
```

**Contract:**
- `prompt`: non-empty user query
- `guidance`: optional rule guidance text (prepended to prompt by GuidanceInjector before reaching agent)
- Returns: generated SQL string
- Raises: `AgentError` on failure

#### `OutcomeEvaluator` (`evaluator.py`)

```python
class OutcomeEvaluator(ABC):
    @abstractmethod
    def evaluate(self, sql: str, context: dict | None = None) -> EvaluationResult: ...
```

**Contract:**
- Input: SQL string + optional context dict
- Output: `EvaluationResult` (classification, reason, patterns detected)
- Raises: `EvaluationError` on failure

#### `ObservationFactory` (`observation.py`)

```python
class ObservationFactory(ABC):
    @abstractmethod
    def create(self, evaluation: EvaluationResult, rule_id: str,
               request_id: str, sql: str, guidance_injected: bool) -> Observation: ...
```

**Contract:**
- Input: evaluation result, identifiers, sql, guidance state
- Output: `Observation` with derived `EvidenceType`
- Raises: `EvidenceStoreError` convention (though labeled as factory)

#### `EvidenceStore` (`evidence.py`)

```python
class EvidenceStore(ABC):
    @abstractmethod
    def append(self, observation: Observation) -> EvidenceRecord: ...
```

**Contract:**
- Input: observation with evidence type, rule_id, request_id
- Output: `EvidenceRecord` with before/after confidence deltas
- Raises: `EvidenceStoreError`

#### `ConfidenceEngine` (`confidence.py`)

```python
class ConfidenceEngine(ABC):
    @abstractmethod
    def update(self, rule_id: str, evidence_type: EvidenceType) -> tuple[float, RuleStatus | None]: ...
```

**Contract:**
- Input: rule identifier, evidence type
- Output: (new_confidence, new_status_or_None)
- Raises: `EvidenceStoreError` if rule not found

#### `RuleRetriever` (`rules.py`)

```python
class RuleRetriever(ABC):
    @abstractmethod
    def retrieve(self, context: RequestContext) -> list[BehavioralRule]: ...
```

**Contract:**
- Input: request context (currently used for semantics; future: pattern matching)
- Output: list of active rules (empty list if none)
- Raises: `RuleRetrievalError`

#### `GuidanceInjector` (`guidance.py`)

```python
class GuidanceInjector(ABC):
    @abstractmethod
    def inject(self, prompt: str, rule: BehavioralRule) -> str: ...
```

**Contract:**
- Input: original prompt + rule containing guidance_text
- Output: prompt with guidance prepended
- Raises: `GuidanceInjectionError`

**Design pattern:** Every interface takes typed domain objects (from `evomind/models/`) as inputs and outputs. No interface exposes raw database cursors, HTTP request objects, or configuration values. This makes every component testable in isolation:

```python
class MockSQLAgent(SQLAgent):
    def generate(self, prompt, guidance=None):
        return "SELECT 1"
```

---

### 3.6 `evomind/models/`

#### Enums (`enums.py`)

```python
class RuleStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"

class EvidenceType(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    BASELINE = "baseline"
    NEUTRAL = "neutral"

class Classification(str, Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    AMBIGUOUS = "ambiguous"
```

All inherit from `str, Enum` for database compatibility (stored as TEXT in SQLite). **Do not add new enum values without adding corresponding cases in the observation factory and confidence engine.**

#### `BehavioralRule` (`behavioral_rule.py`)

```python
@dataclass
class BehavioralRule:
    id: str                          # UUID string
    name: str                        # Human-readable unique name
    guidance_text: str               # The guidance prepended to prompts
    status: RuleStatus               # Current state machine state
    confidence: float                # Current confidence value [0, 1]
    alpha: float                     # Beta distribution alpha (> 0)
    beta: float                      # Beta distribution beta (> 0)
    promotion_threshold: float       # Confidence threshold for candidate→active
    demotion_threshold: float        # Confidence threshold for active→suspended
    min_evidence: int                # Min evidence count for promotion
    supporting_count: int            # Count of supporting evidence
    contradicting_count: int         # Count of contradicting evidence
    version: int                     # Monotonic version number
    created_at: str                  # ISO 8601 timestamp
    updated_at: str                  # ISO 8601 timestamp
```

**Invariants enforced by the database:**
- `alpha > 0 AND beta > 0` (SQL CHECK constraint)
- `confidence BETWEEN 0 AND 1`
- `status IN ('candidate', 'active', 'suspended', 'archived')`

The `version` field increments on every state transition. It is NOT a concurrency control mechanism (SQLite uses no concurrent writers). It exists for telemetry traceability — you can identify which rule version was active during a request.

#### `Observation` (`observation.py`)

```python
@dataclass
class Observation:
    id: str | None                  # UUID string; None before persistence
    request_id: str                 # FK to request_contexts
    rule_id: str                    # FK to behavioral_rules
    classification: Classification  # safe | unsafe | ambiguous
    evidence_type: EvidenceType     # supporting | contradicting | baseline | neutral
    sql_generated: str              # The SQL that was evaluated
    evaluation_reason: str          # Human-readable reason from evaluator
    metadata: dict | None           # Arbitrary additional data
    created_at: str | None          # ISO 8601; None before persistence
```

#### `EvaluationResult` (`evaluation_result.py`)

```python
@dataclass
class EvaluationResult:
    classification: Classification  # safe | unsafe | ambiguous
    reason: str                     # Human-readable explanation
    patterns_detected: list[str]    # List of pattern names detected
```

Note: `patterns_detected` is populated by the evaluator but is NOT currently persisted in the observations table. The `metadata` field on `Observation` is the correct location to store this for future use.

#### `EvidenceRecord` (`evidence_record.py`)

```python
@dataclass
class EvidenceRecord:
    id: str | None                  # UUID string; None before persistence
    observation_id: str             # FK to observations
    rule_id: str                    # FK to behavioral_rules
    evidence_type: EvidenceType     # The evidence type that was recorded
    request_id: str                 # FK to request_contexts
    confidence_before: float        # Rule confidence before update
    confidence_after: float         # Rule confidence after update
    delta: float                    # confidence_after - confidence_before
    created_at: str | None          # ISO 8601; None before persistence
```

**This is the most important data model for observability.** The `delta` field directly quantifies how much a single observation changed the system's belief. A trace explorer query like `evomind.evidence.delta != 0` identifies impactful observations.

#### `RequestContext` (`request_context.py`)

```python
@dataclass
class RequestContext:
    id: str                         # UUID v4 string
    prompt: str                     # Original user prompt
    sql_generated: str              # SQL output from agent
    guidance_injected: bool         # Whether guidance was used
    rule_retrieved_id: str | None   # ID of the rule if retrieved
    rule_retrieved: bool            # Whether any rule was found
    classification: Classification  # Result of evaluation
    trace_id: str                   # OpenTelemetry trace ID (hex)
    created_at: str | None          # ISO 8601; None before persistence
```

#### `LearningState` (`learning_state.py`)

```python
@dataclass
class LearningState:
    id: str | None
    request_id: str
    rule_id: str
    confidence: float
    status: RuleStatus
    supporting_count: int
    contradicting_count: int
    total_evidence: int
    snapshot_at: str | None
```

A point-in-time snapshot created after every evidence update. This table enables time-series queries like "show me confidence over time for rule X." The `LearningStateRepository` can return all snapshots for a rule ordered by `snapshot_at`.

---

### 3.7 `evomind/agent/deterministic_agent.py`

```python
class DeterministicSQLAgent(SQLAgent):
    def __init__(self):
        self._patterns: dict[str, str] = {
            r"\bselect\b.*\bfrom\b": "SELECT * FROM {table} WHERE id = ?",
            r"\binsert\b": "INSERT INTO {table} (name, email, role, status) VALUES (?, ?, ?, ?)",
            r"\bupdate\b": "UPDATE {table} SET name = ?, email = ?, role = ?, status = ? WHERE id = ?",
            r"\bdelete\b": "DELETE FROM {table} WHERE id = ?",
        }
```

**How it works:**

1. If `guidance` is provided — use parameterized SQL with `?` placeholders (SAFE)
2. If no `guidance` — use inline string values (UNSAFE)
3. Prompt is lowercased for keyword matching
4. First matching pattern wins; unsupported prompts return `SELECT 1`

**Example:**

- Prompt: `"show me users"` without guidance → `SELECT * FROM users WHERE id = 123`
- Prompt: `"show me users"` with guidance → `SELECT * FROM users WHERE id = ?`

**Important limitation:** The agent does not understand the prompt content. It only checks for keyword presence. The prompt `"show me users with admin role"` matches `\bselect\b.*\bfrom\b` first and produces the same output as `"show me users"`. This is acceptable for the demo because the evaluator, not the agent, is responsible for SQL safety classification.

---

### 3.8 `evomind/evaluator/sql_safety_evaluator.py`

The evaluator is the most complex single file in the project. It implements 12 detection rules using the `sqlparse` library for AST-level SQL analysis.

```python
class SqlSafetyEvaluator(OutcomeEvaluator):
    DANGEROUS_DDL = [
        "DROP", "TRUNCATE", "ALTER", "CREATE TABLE", "CREATE INDEX",
        "CREATE VIEW", "RENAME", "REINDEX",
    ]
    DANGEROUS_DML_NO_WHERE = ["UPDATE", "DELETE FROM"]
```

**Classification logic:**

1. Parse SQL with `sqlparse.parse(sql)`
2. Check each detection rule in order
3. If any DANGEROUS_DDL pattern found → `UNSAFE`
4. If DANGEROUS_DML without WHERE → `UNSAFE`
5. If string concatenation (`string_agg` or `+` operator) → `UNSAFE`
6. If `--` or `#` comment → `UNSAFE`
7. If `;` stacked query → `UNSAFE`
8. If `LIKE '...%'` with wildcard prefix → `UNSAFE`
9. If tautology (`1=1`, `true`, `1=1 OR 1=1`) → `UNSAFE`
10. If inline literal values found → `UNSAFE`
11. If `COUNT(*)/SELECT *` → `AMBIGUOUS`
12. If function in WHERE → `AMBIGUOUS`
13. If `SLEEP`/`BENCHMARK` → `UNSAFE`
14. If UNION → `AMBIGUOUS`

**Each detection rule is individually tested** in `test_evaluator.py` with boundary cases.

**The `reason` string** is a comma-separated list of detected patterns. Example: `"Inline literal values detected: id=123, Stacked query detected: DROP TABLE"`.

**Non-obvious behavior:** The evaluator returns the LAST classification reason as `result.reason`. It returns all detected patterns in `result.patterns_detected`. The reason is truncated to the last pattern's reason string (implementation detail — the patterns are more useful than the concatenated reason).

**sqlparse AST traversal:** The evaluator uses `stmt.tokens` and `stmt.get_type()` to classify the statement type. Identifier lists are checked for `'*'`. Functions in WHERE are detected by checking if the `Where` token's parent has functions. This is deterministic, tested, and does not execute the SQL.

---

### 3.9 `evomind/observation/observation_factory.py`

The most semantically nuanced component. It implements the three-state evidence model.

```python
class ObservationFactory(ObservationFactory):
    def create(self, evaluation, rule_id, request_id, sql, guidance_injected):
        evidence_type = self._derive_evidence_type(evaluation.classification, guidance_injected)
        return Observation(
            request_id=request_id,
            rule_id=rule_id,
            classification=evaluation.classification,
            evidence_type=evidence_type,
            sql_generated=sql,
            evaluation_reason=evaluation.reason,
            metadata={"patterns_detected": evaluation.patterns_detected},
        )
```

**`_derive_evidence_type()` logic:**

| `guidance_injected` | Classification | Evidence Type | Rationale |
|---|---|---|---|
| False | UNSAFE | SUPPORTING | The rule WAS needed (agent produced unsafe SQL without guidance) |
| False | SAFE | BASELINE | Agent was safe without rule — no evidence about rule effectiveness |
| False | AMBIGUOUS | NEUTRAL | Ambiguous output provides no signal |
| True | SAFE | SUPPORTING | Rule was applied AND agent produced safe SQL — rule worked |
| True | UNSAFE | CONTRADICTING | Rule was applied BUT agent still produced unsafe SQL — rule failed |
| True | AMBIGUOUS | NEUTRAL | Ambiguous output provides no signal |

**Why three states?**

The key insight is the pre-promotion semantics. Before a rule is promoted (guidance NOT injected), unsafe SQL is *supporting* evidence (rule is needed), not *contradicting* evidence (rule failed). If we treated pre-promotion unsafe as contradicting, the rule would never reach the promotion threshold — it would be penalized before it was ever tried.

Conversely, after promotion, safe SQL is *supporting* evidence (rule worked) and unsafe SQL is *contradicting* evidence (rule failed). Pre-promotion safe is *baseline* (no signal) because the agent might have been safe without the rule.

**This semantic distinction is the primary research contribution** of the learning model. Without it, the Beta-Bernoulli update would produce meaningless confidence values.

---

### 3.10 `evomind/learning/`

#### `rule_retriever.py`

```python
class RuleRetriever(RuleRetriever):
    def __init__(self, repository: BehavioralRuleRepository):
        self._repository = repository

    def retrieve(self, context: RequestContext) -> list[BehavioralRule]:
        return self._repository.find_active()
```

Currently retrieves ALL active rules (no prompt matching). The `context` parameter is reserved for future use (e.g., prompt similarity matching). The `find_active()` method queries `WHERE status = 'active'`.

#### `guidance_injector.py`

```python
class GuidanceInjector(GuidanceInjector):
    INJECTION_FORMAT = "{guidance_text}\n\n---\nUser Query: {prompt}"

    def inject(self, prompt: str, rule: BehavioralRule) -> str:
        return self.INJECTION_FORMAT.format(
            guidance_text=rule.guidance_text,
            prompt=prompt,
        )
```

Standard delimiter format: guidance text, blank line, three dashes, blank line, "User Query: " prefix. This format is intentionally simple — in production, you would tune the delimiter for a specific LLM's instruction-following behavior.

#### `evidence_store.py`

```python
class EvidenceStore(EvidenceStore):
    def __init__(self, rule_repo, evidence_repo, learning_state_repo, confidence_engine):
        ...

    def append(self, observation: Observation) -> EvidenceRecord:
        rule = self._rule_repo.find_by_id(observation.rule_id)
        if not rule:
            raise EvidenceStoreError(f"Rule not found: {observation.rule_id}")

        confidence_before = rule.confidence
        new_confidence, new_status = self._confidence_engine.update(
            rule.id, observation.evidence_type
        )
        # Reload rule to get updated values
        rule = self._rule_repo.find_by_id(observation.rule_id)
        delta = rule.confidence - confidence_before

        evidence_record = EvidenceRecord(
            observation_id=observation.id_or_raise,
            rule_id=rule.id,
            evidence_type=observation.evidence_type,
            request_id=observation.request_id,
            confidence_before=confidence_before,
            confidence_after=rule.confidence,
            delta=delta,
        )
        evidence_record = self._evidence_repo.save(evidence_record)

        # Snapshot learning state
        total = rule.supporting_count + rule.contradicting_count
        learning_state = LearningState(
            request_id=observation.request_id,
            rule_id=rule.id,
            confidence=rule.confidence,
            status=rule.status,
            supporting_count=rule.supporting_count,
            contradicting_count=rule.contradicting_count,
            total_evidence=total,
        )
        self._learning_state_repo.save(learning_state)

        return evidence_record
```

**Important sequencing:**

1. Read confidence BEFORE update
2. Call `confidence_engine.update()` which mutates the rule in the database
3. Re-read rule from database to get updated values
4. Calculate delta = after - before
5. Persist evidence record with before/after/delta
6. Snapshot learning state

The two reads of the rule (before and after) are intentional — the confidence engine mutates the database. There is no concurrency issue (single-process SQLite), but the pattern is defensive.

#### `confidence_engine.py`

This is the heart of the learning system. It implements:
1. Beta-Bernoulli confidence update
2. State machine transitions
3. All-or-nothing persistence via database repository calls

**Update method:**

```python
def update(self, rule_id: str, evidence_type: EvidenceType) -> tuple[float, RuleStatus | None]:
    rule = self._repo.find_by_id(rule_id)
    if not rule:
        raise EvidenceStoreError(f"Rule not found: {rule_id}")

    old_status = rule.status
    alpha, beta = rule.alpha, rule.beta

    if evidence_type == EvidenceType.SUPPORTING:
        alpha += 1
    elif evidence_type == EvidenceType.CONTRADICTING:
        beta += 1
    # BASELINE and NEUTRAL: no update

    confidence = alpha / (alpha + beta)

    new_status = self._evaluate_state_transition(
        old_status, confidence, alpha + beta - 2,  # total evidence
        evidence_type, alpha - 1, beta - 1,         # evidence counts
    )

    self._repo.update_confidence(rule_id, confidence, alpha, beta, new_status)
    # If status changed, increment version
    if new_status and new_status != old_status:
        self._repo.update_status(rule_id, new_status)

    return confidence, new_status
```

**State transition evaluation (`_evaluate_state_transition`):**

```python
CANDIDATE:
    if confidence >= promotion_threshold AND total_evidence >= min_evidence:
        → ACTIVE
    else:
        stay CANDIDATE

ACTIVE:
    if confidence < demotion_threshold:
        → SUSPENDED
    else:
        stay ACTIVE

SUSPENDED:
    if confidence >= promotion_threshold:
        → ACTIVE (re-promotion)
    elif evidence_type == CONTRADICTING AND contradicting_count > supporting_count:
        → ARCHIVED
    else:
        stay SUSPENDED

ARCHIVED:
    → ARCHIVED (terminal, no exit)
```

**Key conditions for ARCHIVE:** The rule must be in SUSPENDED state AND the incoming evidence must be CONTRADICTING AND the lifetime contradicting count must exceed the lifetime supporting count. This is a deliberately conservative archive condition — it requires both low confidence AND a specific evidence pattern. A rule can be SUSPENDED indefinitely without being archived.

---

### 3.11 `evomind/orchestration/`

#### `service_registry.py`

```python
class ServiceRegistry:
    def __init__(self):
        self._services: dict[str, Any] = {}

    def register(self, key: str, service: Any) -> None:
        if key in self._services:
            raise ServiceRegistrationError(f"Service already registered: {key}")
        self._services[key] = service

    def resolve(self, key: str) -> Any:
        if key not in self._services:
            raise ServiceRegistrationError(f"Service not found: {key}")
        return self._services[key]
```

A simple string-keyed DI container. No lifecycle management, no proxy, no scope. Registration is one-time; resolution is read-only after startup.

**Registered service keys:**

| Key | Instance |
|---|---|
| `"agent"` | `DeterministicSQLAgent()` |
| `"evaluator"` | `SqlSafetyEvaluator()` |
| `"observation_factory"` | `ObservationFactory()` |
| `"rule_retriever"` | `RuleRetriever(repo)` |
| `"guidance_injector"` | `GuidanceInjector()` |
| `"evidence_store"` | `EvidenceStore(rule_repo, evidence_repo, learning_state_repo, confidence_engine)` |
| `"confidence_engine"` | `ConfidenceEngine(rule_repo)` |

#### `lifecycle.py`

Already covered in section 3.2. Key detail: the shutdown method calls `TracerManager.shutdown()` which calls `self._processor.shutdown()` — this flushes any remaining spans to the exporter. In Docker, the `SIGTERM` handler (default) will trigger this via `@app.on_event("shutdown")`.

#### `orchestrator.py`

The 11-step pipeline:

```python
def process_request(self, prompt: str, mask_sql: bool = False) -> RequestContext:
```

**Step-by-step:**

1. **Validate prompt**: `if not prompt or not prompt.strip()` → raise `OrchestrationError`
2. **Create RequestContext**: UUID v4, null trace_id (filled after span created)
3. **Open root span**: `evomind.request` with version attributes
4. **Set trace_id**: Copy `span.get_span_context().trace_id` to `RequestContext.trace_id`
5. **Retrieve rules**: `RuleRetriever.retrieve(context)` → list (empty or non-empty)
6. **Guidance injection** (conditional): If rules found, `GuidanceInjector.inject(prompt, rule)` → modified prompt
7. **Generate SQL**: `SQLAgent.generate(prompt_with_guidance, guidance_if_any)` → SQL string
8. **Sanitize SQL** (if `mask_sql`): Truncate to `sql_truncation_length`, compute SHA-256 hash, store in span attributes
9. **Evaluate**: `OutcomeEvaluator.evaluate(sql)` → `EvaluationResult`
10. **Create observation**: `ObservationFactory.create(...)` → `Observation`
11. **Persist + update confidence**:
    - Save `RequestContext` to database
    - Save `Observation` to database
    - `EvidenceStore.append(observation)` → `EvidenceRecord`

**Span structure:**

```
evomind.request (root, duration=total)
├── evomind.orchestrator.retrieve_rules (duration=DB query)
├── evomind.orchestrator.inject_guidance (only if rules found)
├── evomind.agent.generate (duration=agent call)
├── evomind.evaluator.evaluate (duration=SQL parse)
├── evomind.observation.create (duration=instant)
├── evomind.evidence.persist_request (duration=DB write)
├── evomind.evidence.persist_observation (duration=DB write)
├── evomind.evidence.append (duration=DB read/write + confidence update)
├── evomind.learning.state_change (only if status transitioned)
└── evomind.lifecycle.complete (duration=instant, summarizer)
```

All spans are siblings under the root span. The root span carries `app.version`, `schema.version`, `rule.version`. The `complete` span carries summary attributes: `app.request.prompt`, `app.request.sql`, `app.request.safety`, `app.request.rule_retrieved`, `app.request.confidence`, `app.request.evidence_type`, `app.request.rule_status`.

**`_sanitize_sql` method:**

```python
def _sanitize_sql(self, sql: str, mask_sql: bool) -> tuple[str, str | None]:
    if not mask_sql:
        return sql, None
    truncated = sql[:self._settings.sql_truncation_length]
    sql_hash = hashlib.sha256(sql.encode()).hexdigest()
    return truncated, sql_hash
```

The hash enables cross-trace SQL correlation without exposing query content. The truncated SQL preserves the first N characters for pattern identification (e.g., "SELECT * FROM users W..." is still identifiable as a SELECT statement).

---

### 3.12 `evomind/persistence/`

#### `database.py`

```python
class Database:
    _local = threading.local()
    _initialized = False

    def initialize(self, db_path: str):
        self._db_path = db_path
        self._local.connection = sqlite3.connect(db_path, check_same_thread=False)
        self._local.connection.row_factory = sqlite3.Row
        self._local.connection.execute("PRAGMA journal_mode=WAL;")
        self._local.connection.execute("PRAGMA foreign_keys=ON;")
        self._initialized = True

    @property
    def connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            raise DatabaseError("Database not initialized")
        return self._local.connection
```

**Threading safety:** `threading.local()` ensures each thread has its own connection. EvoMind is single-process (uvicorn with single worker), but the thread-local pattern prevents cross-contamination if async tasks spill across threads.

**`check_same_thread=False`** is required because the FastAPI async event loop may pass the connection to a different thread than the one that created it. This is technically unsafe for concurrent writes, but there are no concurrent writes in the current architecture (single request processed at a time).

#### `schema.py`

```python
class Schema:
    CREATE_TABLES = {
        "behavioral_rules": """
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
            )
        """,
        "observations": """...""",
        "evidence_records": """...""",
        "request_contexts": """...""",
        "learning_states": """...""",
    }

    INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_observations_request ON observations(request_id)",
        "CREATE INDEX IF NOT EXISTS idx_observations_rule ON observations(rule_id)",
        "CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at)",
        # ... 3 more indexes
    ]
```

**Six indexes on foreign key columns** (`request_id`, `rule_id`) and timestamp columns (`created_at`). No composite indexes — the database size is intentionally small (single-purpose SQLite).

#### `seed.py`

```python
class Seed:
    DEFAULT_RULE = BehavioralRule(
        id=str(uuid4()),
        name="use parameterized queries",
        guidance_text="When generating SQL, always use parameterized queries with ? placeholders instead of inline values. Do not include user input directly in SQL strings.",
        status=RuleStatus.CANDIDATE,
        confidence=0.5,
        alpha=1.0,
        beta=1.0,
        ...
    )
```

Inserted with `INSERT OR IGNORE` to prevent duplicate seed on restart. The GUID is regenerated on every fresh database. If you delete the database file and restart, a new rule with a new ID is created.

#### Repository files (5 files in `repositories/`):

Each repository follows the same pattern:

```python
class BehavioralRuleRepository(BaseRepository):
    def __init__(self, database: Database):
        self._db = database

    def find_all(self) -> list[BehavioralRule]:
        cursor = self._db.connection.execute("SELECT * FROM behavioral_rules")
        return [self._row_to_rule(row) for row in cursor.fetchall()]

    def find_by_id(self, rule_id: str) -> BehavioralRule | None:
        cursor = self._db.connection.execute(
            "SELECT * FROM behavioral_rules WHERE id = ?", (rule_id,)
        )
        row = cursor.fetchone()
        return self._row_to_rule(row) if row else None

    def find_active(self) -> list[BehavioralRule]:
        cursor = self._db.connection.execute(
            "SELECT * FROM behavioral_rules WHERE status = 'active'"
        )
        return [self._row_to_rule(row) for row in cursor.fetchall()]

    def update_confidence(self, rule_id: str, confidence: float, alpha: float, beta: float, status: RuleStatus | None):
        self._db.connection.execute(
            """UPDATE behavioral_rules SET confidence=?, alpha=?, beta=?, status=COALESCE(?, status), updated_at=datetime('now') WHERE id=?""",
            (confidence, alpha, beta, status.value if status else None, rule_id),
        )

    def update_status(self, rule_id: str, status: RuleStatus):
        self._db.connection.execute(
            "UPDATE behavioral_rules SET status=?, version=version+1, updated_at=datetime('now') WHERE id=?",
            (status.value, rule_id),
        )
```

**No commits.** The `Database` class does not auto-commit. All repository operations have `autocommit=False`. The orchestrator does not explicitly commit either. **SQLite's default behavior is auto-commit for DML statements** when using the `connection.execute()` shortcut outside an explicit transaction. This means each repository operation is an independent transaction. If you need atomicity across operations (e.g., save observation + evidence record as a unit), you must use `BEGIN/COMMIT` explicitly.

**This is a known limitation.** The current architecture does not use database transactions across the 11 pipeline steps. If the process crashes between persisting the observation and appending the evidence record, the observation exists in the database without a corresponding evidence record. The orphan is detectable via `LEFT JOIN evidence_records ON observations.id = evidence_records.observation_id WHERE evidence_records.id IS NULL`.

---

### 3.13 `evomind/telemetry/`

#### `tracer_manager.py`

```python
class TracerManager:
    _tracer_provider: TracerProvider | None = None
    _processor: BatchSpanProcessor | None = None

    @classmethod
    def initialize(cls, settings: Settings, exporter: SpanExporter):
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: settings.service_name,
            ResourceAttributes.SERVICE_VERSION: settings.service_version,
            "schema.version": settings.schema_version,
            "rule.version": settings.rule_version,
            "telemetry.distro.version": settings.telemetry_version,
            "telemetry.distro.name": "evomind-observability",
        })
        cls._processor = BatchSpanProcessor(exporter, max_queue_size=2048, max_export_batch_size=512)
        cls._tracer_provider = TracerProvider(resource=resource)
        cls._tracer_provider.add_span_processor(cls._processor)
        trace.set_tracer_provider(cls._tracer_provider)
```

**BatchSpanProcessor parameters:**
- `max_queue_size=2048`: Queue up to 2048 spans before dropping
- `max_export_batch_size=512`: Send up to 512 spans per export request

These are reasonable defaults for demo workloads. For high-throughput production, increase both values and add a scheduled delay.

**`TracerManager.shutdown()`** calls `self._processor.shutdown()` with a 5-second timeout.

#### `meter_manager.py`

```python
class MeterManager:
    @classmethod
    def initialize(cls, settings: Settings):
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: settings.service_name,
            ResourceAttributes.SERVICE_VERSION: settings.service_version,
        })
        cls._meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(cls._meter_provider)
        cls._meter = cls._meter_provider.get_meter(settings.service_name, settings.service_version)
```

#### `exporter_config.py`

```python
class ExporterConfig:
    @staticmethod
    def create_exporter(endpoint: str) -> SpanExporter:
        return OTLPSpanExporter(endpoint=endpoint, timeout=5)
```

5-second timeout. If SigNoz is unreachable, the exporter will timeout after 5 seconds. The BatchSpanProcessor will retry internally with exponential backoff (default 5 retries). After all retries fail, spans are dropped silently.

#### `exception_instrumentor.py`

```python
class ExceptionInstrumentor:
    @staticmethod
    def record_exception(span: Span, error: Exception, attributes: dict | None = None):
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error, attributes=attributes)
```

This is called in two places:
1. The `complete` span in the orchestrator, when any step raises an exception
2. The API layer, when FastAPI returns a 5xx response

#### `span_helper.py`

```python
class SpanHelper:
    SPAN_NAMES = {
        "request": "evomind.request",
        "retrieve_rules": "evomind.orchestrator.retrieve_rules",
        "inject_guidance": "evomind.orchestrator.inject_guidance",
        "generate": "evomind.agent.generate",
        "evaluate": "evomind.evaluator.evaluate",
        "create_observation": "evomind.observation.create",
        "persist_request": "evomind.evidence.persist_request",
        "persist_observation": "evomind.evidence.persist_observation",
        "append_evidence": "evomind.evidence.append",
        "state_change": "evomind.learning.state_change",
        "complete": "evomind.lifecycle.complete",
        "startup": "evomind.system.startup",
        "rule_created": "evomind.rule.created",
    }
```

**`set_span_attribute` helper:**

```python
@staticmethod
def set_span_attribute(span: Span, key: str, value: Any):
    if value is None:
        return
    if isinstance(value, (list, dict)):
        value = json.dumps(value, default=str)
    span.set_attribute(key, value)
```

JSON-serializes list and dict values. This ensures structured data (like `patterns_detected`) is stored as a JSON string in the span attribute.

#### `metrics_registry.py`

```python
class MetricsRegistry:
    _meter = None
    _requests_total: Counter | None = None
    _sql_safety_ratio: ObservableGauge | None = None
    _rule_confidence: ObservableGauge | None = None
    _evidence_count: ObservableGauge | None = None
```

**4 instruments:**

1. **`evomind.requests.total`** — Counter, incremented on every `POST /api/query` (in API layer). Attributes: `classification`, `rule_retrieved`, `guidance_injected`.

2. **`evomind.sql.safety.ratio`** — ObservableGauge, computed as `safe_count / total_count` from the observations table. Attributes: `rule_id`.

3. **`evomind.rule.confidence`** — ObservableGauge, returns current confidence for each rule. Attributes: `rule_id`.

4. **`evomind.rule.evidence.count`** — ObservableGauge, returns `(supporting_count, contradicting_count, total_evidence_count)` per rule. Attributes: `rule_id`, `evidence_type`.

**Callback pattern for ObservableGauges:**

```python
def _get_sql_safety_ratio(self) -> Iterable[Measurement]:
    # Query database for current counts
    safe = execute("SELECT COUNT(*) FROM observations WHERE classification='safe'")
    total = execute("SELECT COUNT(*) FROM observations")
    ratio = safe / total if total > 0 else 1.0
    yield Measurement(ratio, {"rule_id": self._settings.service_name})
```

The gauge callback is invoked by the MeterProvider at each collection interval (default: every 5 seconds). This means the gauge value reflects real-time database state, not request-time snapshots. If the database is under heavy write load, the gauge may lag.

---

### 3.14 `evomind/api/routes.py`

```python
router = APIRouter()

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    service: str = "evomind-observability"

class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User query prompt")
    mask_sql: bool = Field(False, description="Mask sensitive SQL in telemetry")

class QueryResponse(BaseModel):
    request_id: str
    sql: str
    classification: str
    rule_retrieved: bool
    rule_name: str | None
    guidance_injected: bool
    confidence: float

@router.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse()

@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    orchestrator = app.state.lifecycle_manager.resolve("orchestrator")
    try:
        context = orchestrator.process_request(request.prompt, request.mask_sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return context_to_response(context)
```

**Pydantic validation:**
- `prompt`: must be non-empty (`min_length=1`). FastAPI returns 422 for empty/whitespace-only prompts.
- `mask_sql`: boolean, defaults to False.

**`context_to_response`** converts the `RequestContext` (which contains full internal state) to the public `QueryResponse` (which exposes only what a client needs).

**Error handling:** The API layer does NOT catch `EvoMindError` subclasses specifically. All exceptions (including `EvoMindError`, `ValueError`, `KeyError`) are caught by the generic `except Exception` and returned as 500. **This means the stack trace is logged by uvicorn but the client sees only the exception message.**

---

## 4. Test Suite Analysis

### 4.1 Test Configuration (`conftest.py`)

```python
@pytest.fixture
def db():
    database = Database()
    database.initialize(":memory:")
    Schema.create_tables(database.connection)
    Seed.seed(database.connection)
    return database
```

The shared in-memory SQLite fixture is used by 18 of 19 test files. Each test function gets a fresh database. The database is seeded with one default rule (status=CANDIDATE, alpha=1.0, beta=1.0, confidence=0.5).

### 4.2 Test Categories and Coverage

| Test File | Type | Tests | What It Covers |
|---|---|---|---|
| `test_api.py` | Acceptance | ~10 | Health endpoint, query endpoint, empty prompt, missing fields, large payload |
| `test_lifecycle.py` | Acceptance | ~5 | Startup sequence, shutdown sequence, double-startup safety |
| `test_orchestrator.py` | Integration | ~15 | Full 11-step pipeline, mode matrix (guidance/no-guidance × mask/no-mask), error propagation |
| `test_learning_loop.py` | Integration | ~15 | State machine transition sequences, confidence trajectory, archive conditions |
| `test_repositories.py` | Integration | ~10 | CRUD operations, `find_active`, `update_confidence`, `find_by_id` null handling |
| `test_sql_agent.py` | Integration | ~5 | Safe mode, unsafe mode, unsupported prompt, empty prompt |
| `test_telemetry.py` | Integration | ~8 | Span creation, metric recording, exporter fallback |
| `test_config.py` | Unit | ~6 | Default values, env override, frozen attribute violation |
| `test_confidence_engine.py` | Unit | ~20 | Beta-Bernoulli math, state machine transitions, edge cases (all thresholds) |
| `test_database.py` | Unit | ~8 | Initialization, connection access, double-initialization, WAL mode |
| `test_enums.py` | Unit | ~3 | Enum values and membership |
| `test_evaluator.py` | Unit | ~30 | 12 detection rules, boundary cases, safe SQL, empty SQL, None handling |
| `test_evidence_store.py` | Unit | ~10 | Evidence persistence, confidence delta, learning state snapshot |
| `test_exceptions.py` | Unit | ~10 | Exception hierarchy, string representation |
| `test_guidance_injector.py` | Unit | ~5 | Format string output, empty guidance, None handling |
| `test_metrics_registry.py` | Unit | ~6 | Instrument creation, callback registration, gauge computation |
| `test_models.py` | Unit | ~10 | Dataclass construction, default values, enum assignment |
| `test_observation_factory.py` | Unit | ~12 | 6 evidence_type derivations (3×2 matrix) |
| `test_rule_retriever.py` | Unit | ~5 | Active rule filtering, no-active-rules edge case |
| `test_span_helper.py` | Unit | ~8 | Span name constants, attribute formatting, None handling |

**Total: ~214 tests**

### 4.3 Failure Injection Tests (`ops/_validate_failure.py`)

Nine scenarios run independently:

1. **Empty prompt** → `POST /api/query {"prompt": ""}` → 422
2. **Missing prompt field** → `POST /api/query {}` → 422
3. **Whitespace-only prompt** → `POST /api/query {"prompt": "   "}` → 422
4. **None prompt** → `POST /api/query {"prompt": null}` → 422
5. **OTEL unreachable** → Set `EVOMIND_OTEL_ENDPOINT=http://localhost:19999`, start app, send request → should succeed with warning
6. **100 sequential requests** → Time total duration, assert < 5 seconds
7. **Two independent apps** → Start app twice with different ports, send to both → independent state
8. **Large prompt (10K chars)** → Send → should be handled (no length limit enforced)
9. **Settings from env** → Set EVOMIND_* vars, verify settings reflect values

Test 5 (OTEL unreachable) is the most important for resilience. The OTel SDK's OTLP exporter will fail to connect, the BatchSpanProcessor will retry and eventually drop spans, but the application should continue processing requests.

### 4.4 Coverage Report

```
Name                                       Stmts   Miss  Cover
--------------------------------------------------------------
evomind/__init__.py                           1      0   100%
evomind/__main__.py                           5      5     0%
evomind/agent/deterministic_agent.py         36      0   100%
evomind/api/routes.py                        49      1    98%
evomind/app.py                               15      0   100%
evomind/config/settings.py                   21      0   100%
evomind/evaluator/sql_safety_evaluator.py   131      5    96%
evomind/exceptions/errors.py                 27      0   100%
evomind/interfaces/__init__.py                1      1     0%
evomind/interfaces/agent.py                   5      1    80%
evomind/interfaces/confidence.py              5      1    80%
evomind/interfaces/evaluator.py               5      1    80%
evomind/interfaces/evidence.py                5      1    80%
evomind/interfaces/guidance.py                5      1    80%
evomind/interfaces/observation.py             5      1    80%
evomind/interfaces/rules.py                   5      1    80%
evomind/learning/__init__.py                  1      1     0%
evomind/learning/confidence_engine.py         86      0   100%
evomind/learning/evidence_store.py            47      1    98%
evomind/learning/guidance_injector.py         17      0   100%
evomind/learning/rule_retriever.py            13      0   100%
evomind/models/__init__.py                    1      1     0%
evomind/models/behavioral_rule.py             6      0   100%
evomind/models/enums.py                      14      0   100%
evomind/models/evaluation_result.py            6      0   100%
evomind/models/evidence_record.py              6      0   100%
evomind/models/learning_state.py               6      0   100%
evomind/models/observation.py                  7      0   100%
evomind/models/request_context.py              7      0   100%
evomind/observation/__init__.py                1      1     0%
evomind/observation/observation_factory.py    37      0   100%
evomind/orchestration/__init__.py              1      1     0%
evomind/orchestration/lifecycle.py            69      3    96%
evomind/orchestration/orchestrator.py        113      4    96%
evomind/orchestration/service_registry.py      8      0   100%
evomind/persistence/__init__.py                1      1     0%
evomind/persistence/database.py               27      2    93%
evomind/persistence/schema.py                 12      0   100%
evomind/persistence/seed.py                   24      1    96%
evomind/persistence/repositories/__init__.py   1      1     0%
evomind/persistence/repositories/base.py       6      0   100%
evomind/persistence/repositories/behavioral_rule_repo.py  48   0   100%
evomind/persistence/repositories/evidence_record_repo.py  27   1    96%
evomind/persistence/repositories/learning_state_repo.py   18   0   100%
evomind/persistence/repositories/observation_repo.py      27   1    96%
evomind/persistence/repositories/request_context_repo.py  22   0   100%
evomind/telemetry/__init__.py                   1     1     0%
evomind/telemetry/exception_instrumentor.py    10     0   100%
evomind/telemetry/exporter_config.py           9      0   100%
evomind/telemetry/meter_manager.py             15     1    93%
evomind/telemetry/metrics_registry.py          60     1    98%
evomind/telemetry/span_helper.py               31     0   100%
evomind/telemetry/tracer_manager.py            28     3    89%
--------------------------------------------------------------
TOTAL                                       1314   106    92%
```

**Uncovered code analysis:**
- `__main__.py` (0%): The CLI entry point is not tested. Tests import components directly.
- `interfaces/__init__.py` (0%): Empty init file, no code to test.
- `interfaces/*.py` (80%): ABCs — tests cover concrete implementations, interface files are import-only.
- `learning/__init__.py` (0%): Empty init file.
- The missed lines in `orchestrator.py` are the error-recovery branches (lines in the `except` clause). To trigger them, inject a mock component that raises an exception.
- The missed lines in `sql_safety_evaluator.py` are some detection edge cases (empty token lists, unexpected AST structures).

---

## 5. Infrastructure and Deployment

### 5.1 Foundry Deployment (SigNoz)

SigNoz is deployed via **Foundry** (`casting.yaml` at repo root). Foundry manages all SigNoz infrastructure — ClickHouse, ClickHouse Keeper, PostgreSQL, OTel Collector, SigNoz backend, SigNoz frontend (port 8080), and MCP server (port 8000).

```bash
foundryctl cast -f casting.yaml
```

After deployment, create an admin account at `http://localhost:8080`. The OTel collector is available at `localhost:4317` (gRPC) and `localhost:4318` (HTTP).

See [casting.yaml](../casting.yaml) and [Foundry docs](https://github.com/SigNoz/foundry) for details.

### 5.2 Docker Compose (EvoMind App Only)

The EvoMind application runs in its own container, connecting to Foundry's OTel collector:

```
Services:
┌─────────────────────────────────────────────────────┐
│  evomind (./Dockerfile)                             │
│  Ports: 8000 (HTTP)                                 │
│  Env: EVOMIND_OTEL_ENDPOINT=http://host.docker.     │
│        internal:4317                                │
│  Volumes: evomind-data                              │
└─────────────────────────────────────────────────────┘
```

### 5.3 OTel Collector Configuration

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    timeout: 1s
    send_batch_size: 100

exporters:
  clickhouse:
    dsn: tcp://clickhouse:9000
    database: signoz_traces

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse]
```

Both traces and metrics go through the same batch processor and ClickHouse exporter. The batch processor collects spans for 1 second or 100 spans, whichever comes first.

### 5.4 SigNoz Dashboard

File: `ops/signoz-dashboard.json`

10 panels (JSON-encoded chart definitions for SigNoz frontend):

1. **Request Rate** — Time series of requests/minute
2. **SQL Safety Ratio** — Proportion of safe vs unsafe evaluations over time
3. **Confidence Over Time** — Line chart of rule confidence across trace history
4. **Evidence Timeline** — Bar chart of supporting vs contradicting evidence count
5. **State Transitions** — Step chart showing rule state changes
6. **Rule Lifecycle** — Gantt-like chart of candidate/active/suspended/archived durations
7. **Trace Explorer** — Raw trace list with service/operation/duration/status
8. **Request Classification Breakdown** — Pie chart of safe/unsafe/ambiguous
9. **Confidence Delta Distribution** — Histogram of delta values from evidence_records
10. **Performance Timeline** — P50/P95/P99 latency for evomind.request

### 5.4 Dockerfile

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

**Multi-stage?** No — single-stage is sufficient for a demo application. The image size is ~150MB. For production, add a distroless stage.

**`pip install --no-cache-dir .`** installs from `pyproject.toml`. This is run before copying source code, so pip's layer is cached when only source changes.

---

## 6. Architecture Decisions (ADRs)

The following decisions are documented in full in `docs/architecture_decisions.md`. This section provides a condensed reference.

### ADR-1: Python as Implementation Language

**Status:** Accepted  
**Context:** AI/ML ecosystem, OTel SDK maturity  
**Decision:** Use Python 3.10+  
**Consequences:** GIL limits per-process throughput; acceptable for single vertical slice

### ADR-2: FastAPI as API Framework

**Status:** Accepted  
**Context:** Need native OpenAPI, async support, OTel instrumentation  
**Decision:** FastAPI with Pydantic models  
**Consequences:** Automatic OpenAPI docs at `/docs`; input validation via Pydantic

### ADR-3: SQLite with WAL Mode

**Status:** Accepted  
**Context:** Zero-setup, ACID, sufficient for single-process architecture  
**Decision:** SQLite with WAL journal mode, foreign keys, thread-local connections  
**Consequences:** No server process, no network overhead, single-writer limitation

### ADR-4: sqlparse for SQL Analysis

**Status:** Accepted  
**Context:** Need deterministic, non-executing SQL analysis  
**Decision:** Use sqlparse AST traversal; no LLM, no regex-only, no SQL execution  
**Consequences:** Pattern set is finite and manually curated; cannot detect novel injection patterns

### ADR-5: Beta-Bernoulli Confidence Model

**Status:** Accepted  
**Context:** Need interpretable, closed-form Bayesian update  
**Decision:** Beta(α=1, β=1) prior; supporting→α+=1, contradicting→β+=1  
**Consequences:** Simple math, clear interpretation, no gradient computation

### ADR-6: Mock Deterministic Agent

**Status:** Accepted  
**Context:** Zero reproducibility cost, agent is subject not product  
**Decision:** Keyword-mapped mock; guidance → parameterized SQL, no guidance → inline values  
**Consequences:** Not a real LLM; swap via SQLAgent interface for production

### ADR-7: OpenTelemetry for Observability

**Status:** Accepted  
**Context:** Vendor-neutral, unified traces + metrics, strong Python SDK  
**Decision:** OTel SDK with OTLP gRPC exporter  
**Consequences:** Single pipeline for all telemetry; write-only to SigNoz

### ADR-8: Three-State Evidence Semantics

**Status:** Accepted  
**Context:** Prevent baseline safe behavior from incorrectly contradicting rules  
**Decision:** Pre-promotion: unsafe→supporting, safe→baseline; Post-promotion: safe→supporting, unsafe→contradicting  
**Consequences:** More complex mapping but correct confidence values

### ADR-9: Flat Trace Hierarchy

**Status:** Accepted  
**Context:** Flamegraph readability, equal visibility for all lifecycle steps  
**Decision:** All per-request spans as siblings under root span  
**Consequences:** Deep nesting avoided; span duration comparison is direct

### ADR-10: Write-Only Telemetry Pipeline

**Status:** Accepted  
**Context:** SigNoz should never participate in learning loop  
**Decision:** Unidirectional OTel pipeline; SigNoz unreachable → spans dropped, not requests failed  
**Consequences:** Telemetry is best-effort; no rollback or compensating action from SigNoz

---

## 7. Common Pitfalls and Gotchas

### 7.1 Database Transaction Isolation

As noted in section 3.12, each repository operation is its own transaction. If the process crashes between `observation_repo.save()` and `evidence_store.append()`, the observation exists without a corresponding evidence record. **There is no cross-table transaction wrapping the pipeline.**

**Workaround:** In `ops/_validate_failure.py`, detect orphans: `SELECT o.id FROM observations o LEFT JOIN evidence_records e ON o.id = e.observation_id WHERE e.id IS NULL`.

### 7.2 `EvaluationResult` Reason String

The `SqlSafetyEvaluator` collects multiple detected patterns but the `reason` field contains only the last pattern's reason. The `patterns_detected` list contains all patterns. Use `metadata["patterns_detected"]` from the Observation for full pattern data.

### 7.3 `mask_sql` Is Not Retroactive

The `mask_sql` flag controls SQL masking for the current request only. Already-persisted observations retain their original SQL. If you enable `mask_sql` mid-session, early observations contain full SQL and later observations contain truncated + hashed SQL.

### 7.4 Thread-Local Database Connections

`Database._local` is a `threading.local()`. If the application uses multiple worker processes (e.g., uvicorn with `workers=4`), each worker has its own connection to the same SQLite file. SQLite supports multiple readers but only one writer at a time. Concurrent writes will fail with `database is locked`. **Use a single worker.**

### 7.5 Seed Rule ID Regeneration

The default rule's ID is generated anew on every fresh database. If you delete `evomind.db` and restart, the rule gets a new UUID. Any external references to the old rule ID (e.g., dashboard filters) become stale.

### 7.6 OTel SDK Version Compatibility

The OTel Python SDK occasionally introduces breaking changes. The pinned versions in `pyproject.toml` are:

```
opentelemetry-sdk>=1.20.0
opentelemetry-exporter-otlp-proto-grpc>=1.20.0
opentelemetry-api>=1.20.0
```

These version constraints are deliberately loose (`>=` rather than `==`). If upgrading produces errors about missing attributes or changed method signatures, pin to a specific known-good version.

### 7.7 SigNoz Image Tags Are Not Semantic

SigNoz uses two parallel versioning schemes:
- `query-service`: `0.76.2` (semantic-ish)
- `frontend`: `0.76.0-a13d1c89` (version + commit hash)
- `signoz-otel-collector`: `v0.144.6` (OpenTelemetry collector version, not SigNoz version)

The frontend and query-service must be from the same minor version (both `0.76.x`). Mismatched versions cause trace loading errors in the SigNoz UI.

### 7.8 Unicode Rendering in Demo

If the terminal does not support Unicode, the demo output will show mojibake. The demo script (`demo.py`) uses ANSI color codes and Unicode box-drawing characters (┌─┐│└┘). To disable, set `NO_COLOR=1` or `TERM=dumb`.

### 7.9 Test Database Isolation

Tests use `":memory:"` SQLite databases. Each test function gets a fresh database via fixture. However, if a test fails mid-way, the database connection may not be properly cleaned up. The fixture uses `yield` pattern with shutdown in the teardown:

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

If `database.close()` raises an exception (connection already closed), it will mask the test failure. This is a known minor issue.

### 7.10 `Version` Field Increment

The `version` field on `BehavioralRule` increments by 1 on every status transition (via `update_status`). However, the `update_confidence` method (called on every evidence update) does NOT increment version. This means version is a count of state transitions, not evidence updates. Two rules with the same version number may have different evidence counts.

---

## 8. Operational Runbook

### 8.1 Quick Start (30 seconds)

```bash
# Clone and install
git clone <repo>
cd evomind-observability
pip install .

# Run automated demo
python demo.py --auto
```

Expected output: 6 requests showing the learning lifecycle, ending with "Demo complete."

### 8.2 Start with SigNoz Observability

```bash
# Start SigNoz stack
docker compose up -d clickhouse query-service frontend signoz-otel-collector

# Wait for SigNoz to be ready (verify on http://localhost:8080)
# Start EvoMind with OTEL enabled
python demo.py --auto --host localhost --port 8000
```

### 8.3 Start Without Docker (Standalone)

```bash
export EVOMIND_OTEL_ENDPOINT=http://localhost:4317
python demo.py --auto
```

If SigNoz is not running, trace export will timeout silently. The demo will still succeed.

### 8.4 Run Tests

```bash
# All tests
pytest -v

# With coverage
pytest --cov=evomind --cov-report=term-missing

# Specific category
pytest tests/unit/
pytest tests/integration/
pytest tests/acceptance/
```

### 8.5 Check Database State

```bash
# Open SQLite shell
sqlite3 evomind.db

# Show all observations with rule status
SELECT o.id, o.classification, o.evidence_type, br.status, br.confidence
FROM observations o
JOIN behavioral_rules br ON o.rule_id = br.id;

# Show all evidence records with confidence deltas
SELECT e.id, e.evidence_type, e.confidence_before, e.confidence_after, e.delta
FROM evidence_records e;

# Show learning state history
SELECT * FROM learning_states ORDER BY snapshot_at;
```

### 8.6 Reset Learning State

```bash
# Delete database and restart
rm evomind.db
python demo.py --auto

# Or reset rule to candidate via SQLite
sqlite3 evomind.db "UPDATE behavioral_rules SET status='candidate', confidence=0.5, alpha=1.0, beta=1.0, supporting_count=0, contradicting_count=0, version=1;"
```

### 8.7 Common Debug Commands

```bash
# Check if OTEL endpoint is reachable
python -c "from opentelemetry.exporter.otlp.proto.grpc.exporter import OTLPSpanExporter; e = OTLPSpanExporter(endpoint='http://localhost:4317', timeout=2); print('OK' if e else 'FAIL')"

# View current rule state
python -c "
from evomind.persistence.database import Database
from evomind.persistence.repositories.behavioral_rule_repo import BehavioralRuleRepository
from evomind.config.settings import get_settings
db = Database(); db.initialize(get_settings().db_path or ':memory:')
from evomind.persistence.schema import Schema; Schema.create_tables(db.connection)
from evomind.persistence.seed import Seed; Seed.seed(db.connection)
repo = BehavioralRuleRepository(db)
for rule in repo.find_all():
    print(f'{rule.name}: status={rule.status.value}, confidence={rule.confidence:.3f}, α={rule.alpha}, β={rule.beta}')
"

# Inspect latest traces via OTel
# (Requires OTel SDK CLI or custom script)
python -c "
from evomind.telemetry.tracer_manager import TracerManager
from evomind.telemetry.exporter_config import ExporterConfig
from evomind.config.settings import get_settings
settings = get_settings()
exp = ExporterConfig.create_exporter(settings.otel_endpoint)
print(f'Exporter: {type(exp).__name__}, endpoint: {settings.otel_endpoint}')
"
```

### 8.8 Performance Characteristics

| Operation | Typical Duration (SQLite) | Notes |
|---|---|---|
| Single pipeline (no DB) | ~1-2ms | Pure Python, no IO |
| With DB writes | ~5-10ms | SQLite WAL write |
| With OTel export | ~2-5ms + ~50ms async | Synchronous create, async export |
| 100 sequential requests | ~1.10s | Confirmed by failure validation |
| Database file size | ~50KB after 100 requests | Negligible |

### 8.9 Health Check Endpoint

```bash
curl http://localhost:8000/api/health
# Response: {"status":"ok","version":"0.1.0","service":"evomind-observability"}
```

If the application fails during startup (e.g., database initialization error), the health check will not respond (uvicorn will return 503).

### 8.10 Query Endpoint Examples

```bash
# Basic query (will use inline SQL — unsafe)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "show me users"}'

# Query with mask_sql enabled
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "show me users", "mask_sql": true}'

# Invalid (empty prompt)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": ""}'
# Response: 422
```

---

## Appendix A: Complete Interface Contracts

```
SQLAgent.generate(prompt: str, guidance: str | None = None) → str
    Raises: AgentError

OutcomeEvaluator.evaluate(sql: str, context: dict | None = None) → EvaluationResult
    Raises: EvaluationError
    EvaluationResult: {classification, reason, patterns_detected}

ObservationFactory.create(evaluation, rule_id, request_id, sql, guidance_injected) → Observation
    Observation: {id, request_id, rule_id, classification, evidence_type, sql_generated, evaluation_reason, metadata, created_at}

EvidenceStore.append(observation: Observation) → EvidenceRecord
    Raises: EvidenceStoreError
    EvidenceRecord: {id, observation_id, rule_id, evidence_type, request_id, confidence_before, confidence_after, delta, created_at}

ConfidenceEngine.update(rule_id: str, evidence_type: EvidenceType) → tuple[float, RuleStatus | None]
    Raises: EvidenceStoreError
    Returns: (new_confidence, new_status_or_None_if_no_transition)

RuleRetriever.retrieve(context: RequestContext) → list[BehavioralRule]
    Raises: RuleRetrievalError

GuidanceInjector.inject(prompt: str, rule: BehavioralRule) → str
    Raises: GuidanceInjectionError
```

---

## Appendix B: Database Schema DDL

```sql
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

Indexes: idx_observations_request, idx_observations_rule, idx_observations_created, idx_evidence_request, idx_evidence_rule, idx_learning_state_rule.

---

## Appendix C: Complete Enum Reference

```
RuleStatus:
  CANDIDATE   → "candidate"   (initial state, evidence being collected)
  ACTIVE      → "active"      (retrieved on requests, guidance injected)
  SUSPENDED   → "suspended"   (not retrieved, can be re-promoted)
  ARCHIVED    → "archived"    (terminal state, permanently retired)

EvidenceType:
  SUPPORTING   → "supporting"    (evidence that the rule is needed/works)
  CONTRADICTING → "contradicting" (evidence that the rule failed)
  BASELINE     → "baseline"      (pre-promotion safe — no signal)
  NEUTRAL      → "neutral"       (ambiguous classification — no signal)

Classification:
  SAFE       → "safe"       (no dangerous patterns detected)
  UNSAFE     → "unsafe"     (destructive patterns detected)
  AMBIGUOUS  → "ambiguous"  (non-destructive patterns detected)
```

---

## Appendix D: Span Attributes Reference

| Span Name | Attributes |
|---|---|
| `evomind.request` | `app.version`, `schema.version`, `rule.version`, `telemetry.version` |
| `evomind.orchestrator.retrieve_rules` | `rule.count` |
| `evomind.orchestrator.inject_guidance` | `rule.id`, `rule.name` |
| `evomind.agent.generate` | (none) |
| `evomind.evaluator.evaluate` | `app.result.classification` |
| `evomind.observation.create` | `app.result.classification`, `app.result.evidence_type` |
| `evomind.evidence.persist_request` | `request.id` |
| `evomind.evidence.persist_observation` | `observation.id` |
| `evomind.evidence.append` | `evidence.delta`, `evidence.before`, `evidence.after` |
| `evomind.learning.state_change` | `rule.status.from`, `rule.status.to` |
| `evomind.lifecycle.complete` | `app.request.prompt`, `app.request.sql`, `app.request.safety`, `app.request.rule_retrieved`, `app.request.confidence`, `app.request.evidence_type`, `app.request.rule_status` |
| `evomind.system.startup` | (none) |
| `evomind.rule.created` | `rule.id`, `rule.name`, `rule.version` |

---

*End of Technical Handover Document. For permanent reference, see DELIVERABLE_3_ARCHITECTURE_BOOK.md.*
