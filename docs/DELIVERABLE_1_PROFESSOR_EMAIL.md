# Deliverable 1: Professor Email

**To:** Professor [Name], Department of Computer Science  
**From:** 
**Subject:** EvoMind Observability — Final Engineering Handover and Architecture Overview

---

Dear Professor,

I am writing to document the complete engineering deliverable for the EvoMind Observability project. This email describes what was built, why it was built, the architectural decisions that shaped it, and the research questions it answers. The repository is now frozen and ready for submission.

---

## Project Overview

EvoMind Observability is a debugger for AI behavioral learning. It makes the learning lifecycle of an AI agent observable as a production system. The core claim is: "The behavioral learning lifecycle of an AI agent can be represented as an observable production system." We are not claiming autonomous learning. We are claiming that learning can be made observable — every evidence signal, confidence delta, and rule transition can be traced, queried, and investigated without reading source code.

The repository implements one complete vertical slice: one agent (a secure SQL assistant), one domain (SQL query generation), one repeated behavioral mistake (string interpolation), one behavioral rule ("use parameterized queries"), one learning lifecycle (evidence accumulation, confidence update, rule promotion, guidance injection, behavior improvement), and one observability pipeline (OpenTelemetry to SigNoz).

---

## Problem Statement and Research Motivation

**The fundamental problem:** When an AI agent is deployed and begins making mistakes, there is no standard way to observe, measure, and correct its behavioral drift. Traditional approaches fall into two failure modes:

1. **Black-box fine-tuning:** Retrain the model on corrected examples. This is expensive, opaque, and does not provide per-request traceability. An engineer cannot determine which specific input caused which specific behavioral change.

2. **Log-based debugging:** Scrape application logs for error patterns. This is unstructured, lacks type safety, and cannot express the causal chain from observation to behavior change. Logs do not capture confidence, evidence accumulation, or state transitions.

EvoMind Observability addresses both failure modes by treating behavioral learning as an observable state machine with structured telemetry at every transition point. The innovation is not in the learning algorithm (which is deliberately simple — Beta-Bernoulli) but in the observability layer: every lifecycle step emits a named OpenTelemetry span with typed attributes, enabling an engineer to reconstruct the complete behavioral history of a rule using only a SigNoz dashboard.

---

## System Architecture

The architecture is a sequential pipeline coordinator with eight pluggable components, each defined by an abstract interface. The Orchestrator is the sole coordinator; no component communicates with any other component directly. Information flows in one direction: request-in, response-out, with telemetry emitted to a unidirectional OpenTelemetry pipeline.

The component stack:

- **Config Layer** (`evomind/config/settings.py`): Pydantic-based settings with environment variable overrides (`EVOMIND_*`). All thresholds, versions, telemetry endpoints, and privacy flags are configurable. The settings object is frozen after construction.

- **Models Layer** (`evomind/models/`): Six dataclass entities — `BehavioralRule` (with alpha/beta confidence parameters and state machine transitions), `Observation` (a single evaluation outcome), `EvidenceRecord` (persisted link between observation and rule), `EvaluationResult` (transient value object from the evaluator), `RequestContext` (captures the full request lifecycle), and `LearningState` (point-in-time snapshot). Three enums: `RuleStatus` (candidate, active, suspended, archived), `EvidenceType` (supporting, contradicting, baseline, neutral), `Classification` (safe, unsafe, ambiguous).

- **Interfaces Layer** (`evomind/interfaces/`): Seven abstract base classes defining the contracts for every pluggable component — `SQLAgent`, `OutcomeEvaluator`, `ObservationFactory`, `EvidenceStore`, `ConfidenceEngine`, `RuleRetriever`, `GuidanceInjector`. Each interface file specifies input/output types, error conditions, and docstring contracts.

- **Agent** (`evomind/agent/`): `DeterministicSQLAgent` implements `SQLAgent`. A keyword-matching mock with two modes: without guidance, it produces SQL with inline values (unsafe, e.g., `SELECT * FROM users WHERE id = 123`); with guidance, it produces parameterized SQL (safe, e.g., `SELECT * FROM users WHERE id = ?`). This is a deliberate design choice for reproducibility — the agent is the subject under observation, not the product.

- **Evaluator** (`evomind/evaluator/`): `SqlSafetyEvaluator` implements `OutcomeEvaluator`. Uses the `sqlparse` library for deterministic AST-level analysis. Detects 12 pattern classes: dangerous DDL, dangerous DML without WHERE, string concatenation, SQL comments, stacked queries, LIKE with wildcard prefix, tautologies (`1=1`), `SELECT *`, inline values, functions in WHERE, sleep/benchmark functions, UNION injection. Classification: safe (no patterns detected), unsafe (destructive patterns detected), ambiguous (non-destructive patterns detected).

- **Observation Factory** (`evomind/observation/`): `ObservationFactory` implements the three-state evidence semantics. Pre-promotion (no guidance injected): unsafe→supporting, safe→baseline, ambiguous→neutral. Post-promotion (guidance injected): safe→supporting, unsafe→contradicting, ambiguous→neutral. This semantic distinction prevents baseline safe behavior from incorrectly contradicting a rule that has not yet been tested.

- **Learning Engine** (`evomind/learning/`): Contains `EvidenceStore` (persists observations as evidence records with before/after confidence deltas), `ConfidenceEngine` (Beta-Bernoulli update: supporting→α+=1, contradicting→β+=1, baseline/neutral→no update; confidence = α/(α+β)), `GuidanceInjector` (prepends rule guidance text to the user prompt with a standard delimiter format), and `RuleRetriever` (queries the repository for rules with status=ACTIVE).

- **Orchestration** (`evomind/orchestration/`): `ServiceRegistry` is a simple dependency injection container (register/resolve by string key). `LifecycleManager` handles startup sequencing: telemetry initialization (TracerProvider + MeterProvider + BatchSpanProcessor + MetricsRegistry), database initialization (SQLite WAL mode + schema creation + rule seeding), and core service registration. `Orchestrator` is the 11-step pipeline that coordinates every request through the full lifecycle.

- **Persistence** (`evomind/persistence/`): `Database` wraps SQLite with WAL journal mode, foreign keys enforced, thread-local connections, and row factory. `Schema` defines 5 tables with CHECK constraints, foreign keys, and 6 indexes. `Seed` creates the default behavioral rule at startup. Five repository classes provide CRUD for each entity.

- **Telemetry** (`evomind/telemetry/`): `TracerManager` initializes the OpenTelemetry TracerProvider with versioned resource attributes. `MeterManager` initializes the MeterProvider for metrics. `ExporterConfig` creates an OTLP gRPC span exporter. `SpanHelper` provides consistent span creation, attribute setting (with JSON serialization for list/dict values), and error recording. `ExceptionInstrumentor` implements the uniform exception policy. `MetricsRegistry` manages 4 instruments: `evomind.requests.total` (Counter), `evomind.sql.safety.ratio` (ObservableGauge), `evomind.rule.confidence` (ObservableGauge), `evomind.rule.evidence.count` (ObservableGauge).

- **API** (`evomind/api/`): FastAPI router with two endpoints: `GET /api/health` (returns status, version, service name) and `POST /api/query` (accepts `{prompt, mask_sql?}`, returns request_id, sql, classification, rule_retrieved, rule_name, guidance_injected, confidence). Input validation via Pydantic models. Returns 422 for invalid input, 500 for internal failures.

---

## The Runtime Request Lifecycle

A single request traverses exactly 11 steps:

1. Prompt validated (non-empty check in `process_request`)
2. `RequestContext` created with UUID v4 and OTel trace_id
3. Root span `evomind.request` opened with version metadata
4. `RuleRetriever.retrieve()` called — queries repository for ACTIVE rules
5. If rules found, `GuidanceInjector.inject()` prepends guidance text to prompt
6. `DeterministicSQLAgent.generate()` called — with guidance produces parameterized SQL, without guidance produces inline-value SQL
7. `SqlSafetyEvaluator.evaluate()` classifies SQL via sqlparse AST analysis
8. `ObservationFactory.create()` derives evidence type from classification and guidance state
9. `RequestContext` and `Observation` persisted to SQLite
10. `EvidenceStore.append()` creates `EvidenceRecord` with before/after confidence
11. `ConfidenceEngine.update()` applies Beta-Bernoulli update and checks state transitions (Candidate→Active, Active→Suspended, Suspended→Active, Suspended+Contradicting→Archived)

Throughout these steps, 9 child spans are opened and closed as children of the root span. Conditional spans exist for guidance injection (only if rule retrieved) and state change (only if status changes). A final `evomind.lifecycle.complete` span summarizes the request. Metrics counters are incremented at three emission points: request classification, confidence value, evidence count.

---

## The Beta-Bernoulli Confidence Model

The confidence model is the simplest fully-Bayesian conjugate model available:

- Prior: Beta(α=1.0, β=1.0) — the uniform prior, encoding no prior belief
- Supporting evidence (rule needed or rule worked): α += 1
- Contradicting evidence (rule failed): β += 1
- Baseline/neutral: no update
- Confidence = E[Beta(α, β)] = α / (α + β)

Key properties: Confidence approaches 1.0 asymptotically with all-supporting evidence, approaches 0.0 with all-contradicting evidence, and stays at 0.5 with equal evidence. The prior sample size of 2 ensures that approximately 2 observations are needed to move confidence meaningfully away from 0.50.

Thresholds: Promotion at confidence >= 0.75 with at least 3 total evidence. Demotion at confidence < 0.35. Archive when SUSPENDED + CONTRADICTING evidence + contradicting_count > supporting_count. Thresholds are asymmetric to create hysteresis — the rule is "sticky" once promoted, preventing oscillation.

---

## The State Machine

Four states: CANDIDATE (initial, not retrieved, evidence being collected), ACTIVE (retrieved on every matching request, guidance injected into prompt), SUSPENDED (not retrieved, can be re-promoted), ARCHIVED (terminal, permanently retired).

Transitions: CANDIDATE→ACTIVE (confidence >= 0.75 AND evidence >= 3), ACTIVE→SUSPENDED (confidence < 0.35), SUSPENDED→ACTIVE (re-promotion, confidence >= 0.75), SUSPENDED→ARCHIVED (contradicting evidence received AND contradicting_count > supporting_count).

---

## Observability Architecture

Spans: 12 named spans total — 2 startup (evomind.system.startup, evomind.rule.created) and 10 per-request. The per-request trace hierarchy is flat (siblings under root span), intentionally avoiding deep nesting for flamegraph visibility.

All spans carry version metadata: `app.version`, `schema.version`, `rule.version`, `telemetry.version`. This enables cross-deployment debugging and schema evolution tracking.

Four metric instruments: Counter for request totals, ObservableGauge for SQL safety ratio (safe/total), ObservableGauge for current rule confidence, ObservableGauge for evidence count.

The telemetry pipeline: Python OpenTelemetry SDK → OTLP gRPC (port 4317) → SigNoz OTel Collector → ClickHouse storage → SigNoz frontend (port 8080). The collector configuration uses batching (1s timeout, 100 batch size). Metrics and traces share the same pipeline.

The masked SQL feature (`mask_sql=true`) truncates raw SQL to `sql_truncation_length` characters (default 200) and emits a SHA-256 hash in the `sql.hash` attribute for cross-trace correlation without exposing content.

---

## Database Schema

Five SQLite tables with WAL journal mode and foreign key enforcement:

- `behavioral_rules`: id (PK), name (UNIQUE), guidance_text, status (CHECK candidate/active/suspended/archived), confidence (0-1), alpha (>0), beta (>0), promotion_threshold, demotion_threshold, min_evidence, supporting_count, contradicting_count, timestamps
- `observations`: id (PK), request_id (FK→request_contexts), rule_id (FK→behavioral_rules), classification, evidence_type, sql_generated, evaluation_reason, metadata (JSON), created_at
- `evidence_records`: id (PK), observation_id (FK→observations), rule_id (FK→behavioral_rules), evidence_type, request_id (FK→request_contexts), confidence_before, confidence_after, delta, created_at
- `request_contexts`: id (PK), prompt, sql_generated, guidance_injected, rule_retrieved_id (FK), rule_retrieved (boolean), classification, trace_id, created_at
- `learning_states`: id (PK), request_id (FK→request_contexts), rule_id (FK→behavioral_rules), confidence, status, supporting_count, contradicting_count, total_evidence, snapshot_at

Six indexes on foreign key and timestamp columns.

---

## Testing Infrastructure

214 tests across 19 test files, achieving 92% line coverage. Test categories:

- **Unit tests**: Models, enums, config, exceptions, evaluator (12 detection patterns individually tested), guidance injector, observation factory, evidence store, confidence engine, rule retriever, metrics registry
- **Integration tests**: Orchestrator (full pipeline validation), learning loop (state machine transitions), repositories (CRUD operations), SQL agent (safe/unsafe mode matrix), telemetry
- **Acceptance tests**: API endpoints (health, query, error handling), startup/shutdown lifecycle, DI container, database initialization
- **Failure injection**: 9 scenarios (empty/missing/whitespace/None prompt all return 422, OTEL unreachable still works, 100 sequential requests in 1.10s, two independent apps work)

The test conftest provides a shared SQLite in-memory database fixture with full schema creation.

---

## Infrastructure

**Docker Compose** (`docker-compose.yml`): EvoMind app only (Python 3.10-slim image). SigNoz services (ClickHouse, query-service, frontend, OTel collector) are deployed via Foundry (`casting.yaml`). All images pinned to explicit versions. Networks, volumes, and health checks configured.

**Dockerfile**: Multi-stage Python 3.10-slim build. Installs pyproject.toml dependencies, copies evomind package, exposes port 8000.

**SigNoz Dashboard** (`ops/signoz-dashboard.json`): 10 panels — request rate, SQL safety ratio over time, confidence over time, evidence timeline, state transitions, rule lifecycle, trace explorer, request classification breakdown, confidence delta distribution, performance timeline.

---

## Files Created (Complete Inventory)

**Production source (21 files):**
- `evomind/__init__.py`, `__main__.py`, `app.py` — Application entry points
- `evomind/config/settings.py` — Configuration model
- `evomind/exceptions/__init__.py`, `errors.py` — Typed exception hierarchy (10 classes)
- `evomind/interfaces/__init__.py` + 7 interface files — Abstract contracts
- `evomind/agent/deterministic_agent.py` — Mock SQL agent
- `evomind/models/__init__.py` + 7 model files — Domain entities
- `evomind/evaluator/sql_safety_evaluator.py` — SQL safety classifier
- `evomind/observation/observation_factory.py` — Evidence type derivation
- `evomind/learning/__init__.py` + 4 learning files — Learning engine
- `evomind/orchestration/__init__.py` + 3 files — Orchestrator, registry, lifecycle
- `evomind/persistence/__init__.py` + 3 files + 5 repository files — Persistence layer
- `evomind/telemetry/__init__.py` + 6 files — Telemetry layer
- `evomind/api/__init__.py`, `routes.py` — FastAPI endpoints

**Tests (19 files):** Complete test suite with acceptance, unit, and integration coverage.

**Architecture documentation (11 files):** Executive summary, architecture, data model, state machines, confidence model, SQL evaluator, telemetry model, API contracts, testing strategy, demo plan, architecture decisions.

**Top-level documentation (7 files):** README (judge-focused), DEMO.md, JUDGE_GUIDE.md, OBSERVABILITY_GUIDE.md, TRACE_WALKTHROUGH.md, HACKATHON_SUBMISSION_AUDIT.md, RELEASE_VALIDATION_REPORT.md.

**Infrastructure (5 files):** Dockerfile, docker-compose.yml, ops/otel-collector-config.yaml, ops/signoz-dashboard.json, ops/_validate_failure.py.

---

## Engineering Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.10+ | Best OTel SDK maturity, AI/ML audience expectations |
| API framework | FastAPI | Native async, built-in OpenAPI, first-class OTel integration |
| Storage | SQLite (WAL) | Zero setup, ACID, sufficient for single vertical slice |
| SQL parser | sqlparse | Deterministic, mature, AST-level analysis without execution |
| Confidence model | Beta-Bernoulli | Fully Bayesian, interpretable, closed-form update |
| Agent | Mock deterministic | Zero cost, fully reproducible, agent is the subject not the product |
| Telemetry | OpenTelemetry | Vendor-neutral, single SDK for traces + metrics |
| Observability backend | SigNoz | OTel-native, open-source, ClickHouse-backed |
| Trace structure | Flat siblings | Every lifecycle step equally visible in flamegraph |
| Evidence semantics | Three-state | Prevents baseline safe behavior from incorrectly contradicting rules |
| Write-only telemetry | Unidirectional | SigNoz never participates in learning loop |
| Architecture | Frozen | No new features permitted after Phase 5 |

---

## What Has Intentionally NOT Been Implemented

- **Multi-rule support**: The system is designed for N rules (interfaces support lists, repositories support filters) but only one rule is seeded. Automatic rule discovery is explicitly out of scope.
- **Real LLM agent**: The mock agent is replaceable via the `SQLAgent` interface. A real LLM would add non-determinism and API costs without changing the observability layer.
- **Authentication/authorization**: No auth layer. The API is designed for local demo only.
- **Horizontal scaling**: SQLite limits writes to a single process. PostgreSQL replacement would be required for production.
- **CI/CD pipeline**: No GitHub Actions or similar. Coverage and lint badges are not implemented.
- **Adaptive thresholds**: Thresholds are static and configurable. Self-tuning thresholds would violate the write-only telemetry principle.

---

## Project Metrics

- **Source files**: 21 production Python files (approximately 1,319 statements)
- **Test files**: 19 test files with 214 test cases
- **Coverage**: 92% line coverage
- **Architecture docs**: 11 documents covering every design dimension
- **Top-level docs**: 7 documents (judge guides, walkthroughs, audit checklists)
- **API endpoints**: 2 (health + query)
- **Database tables**: 5, with 6 indexes
- **Telemetry spans**: 12 named spans (2 startup + 10 per-request)
- **Metric instruments**: 4 (1 counter + 3 observable gauges)
- **Docker services**: 5 (ClickHouse, query-service, frontend, OTel collector, EvoMind)
- **Configuration options**: 18 environment variables
- **Evidence types**: 4 (supporting, contradicting, baseline, neutral)
- **Rule states**: 4 (candidate, active, suspended, archived)
- **Detection rules**: 12 SQL safety patterns
- **Exception types**: 10 typed exception classes

---

## Future Research Directions

1. **Multi-rule arbitration**: When multiple behavioral rules match a single request, how should guidance be combined or prioritized? This requires a rule priority system and conflict resolution protocol.

2. **Automatic pattern discovery**: Mining observations to discover candidate behavioral rules automatically, rather than seeding them manually. This would require clustering, frequent pattern mining, or LLM-based analysis.

3. **Cross-session learning**: Persisting a rule's confidence across application restarts and correlating it with telemetry from previous deployment versions.

4. **Causal inference**: Determining not just that behavior changed, but why — disentangling the effects of guidance injection from other factors (prompt variation, model updates, context drift).

5. **Adaptive thresholds**: Using observed evidence distributions to dynamically set promotion and demotion thresholds per rule, based on historical confidence trajectories.

---

The repository is complete, frozen, and ready for submission. All 214 tests pass at 92% coverage. The working tree is clean. Every Phase 3-5 file is committed. A judge can clone the repository and run `python demo.py --auto` within 2 minutes to observe the full learning lifecycle.

Best regards,

