# EvoMind Observability — Architecture

## Architectural Principles

### 1. Single Responsibility
Every component does exactly one thing. The SQL Agent generates SQL. The Outcome Evaluator classifies SQL. The Confidence Engine computes confidence. No component crosses boundaries.

### 2. Deterministic Evaluation
All SQL safety evaluations are rule-based, deterministic, and repeatable. The same SQL always produces the same classification. No ML, no heuristics, no randomness.

### 3. Observability First
Every lifecycle transition emits telemetry. If a transition is not observable in SigNoz, it does not exist. Observability is not added after the fact — it is designed into every interface.

### 4. Loose Coupling
Components communicate through well-defined contracts (see API Contracts). No component imports or depends on another component's internals. The Orchestrator is the only coordinator.

### 5. Write-Only Telemetry
Telemetry flows in one direction: system → OpenTelemetry SDK → SigNoz. SigNoz never writes back to the system. No feedback loop. No query-for-decision.

### 6. Reproducibility
Given the same input sequence, the system produces identical outputs and telemetry. The mock agent, deterministic evaluator, and SQLite storage together guarantee reproducibility.

### 7. Explainability
Every numeric value (confidence, threshold, evidence count) can be traced to specific observations. No black-box computation. The confidence formula is a simple Beta-Bernoulli ratio.

### 8. Extensibility
Interfaces are designed for `N` rules, `N` agents, and `N` evidence types — even though the hackathon implements exactly one of each. No component hardcodes the "one rule" constraint at the interface level.

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER / CLIENT                           │
│                  (curl, script, or UI)                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │ POST /api/query  {prompt: "..."}
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                            │
│                                                                  │
│  Coordinates lifecycle. Owns the trace. Calls components.        │
│  No business logic — only orchestration.                         │
└──┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐     │
   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼
┌──────┐┌──────┐┌────┐┌──────┐┌─────┐┌──────┐┌──────┐┌──────┐
│Rule  ││Guide ││SQL ││Outcme││Obsrv││Evidnc││Conf  ││Rule  │
│Retrvr││Inject││Agnt││Evalu ││Fact ││Store ││Engine││Regstr│
└──────┘└──────┘└────┘└──────┘└────┘└──────┘└──────┘└──────┘
   │       │       │       │       │       │       │       │
   └───────┴───────┴───────┴───────┴───────┴───────┴───────┘
                              │
                              ▼
               ┌──────────────────────────┐
               │     TELEMETRY LAYER      │
               │  (OpenTelemetry Python)   │
               │  OTLP Exporter → gRPC     │
               └──────────┬───────────────┘
                          │ OTLP :4317
                          ▼
               ┌──────────────────────────┐
               │       SIGNOZ             │
               │  (OTel Collector →        │
               │   ClickHouse → Frontend)  │
               └──────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility |
|---|---|
| **Orchestrator** | Receives requests, coordinates lifecycle, owns the OTel trace, returns responses |
| **SQL Agent** | Accepts a prompt + optional guidance, returns generated SQL string. Deterministic mock for hackathon. |
| **Outcome Evaluator** | Accepts a SQL string, returns classification (safe/unsafe/ambiguous) with reason |
| **Observation Factory** | Accepts an EvaluationResult + RequestContext, returns a structured Observation |
| **Evidence Store** | Persists Observation as evidence for/against a rule. Supports append, query, summary. |
| **Confidence Engine** | Reads all evidence for a rule, computes Beta-Bernoulli confidence, updates rule |
| **Behavioral Rule Registry** | CRUD for BehavioralRules, manages state transitions, tracks confidence history |
| **Rule Retriever** | Queries registry for Active rules matching the current context, returns ordered list |
| **Guidance Injector** | Accepts a prompt + list of rules, returns modified prompt with injected guidance |
| **Telemetry Layer** | Wraps every component call in OTel spans, emits metrics, manages trace context |
| **SigNoz** | Receives OTel telemetry, stores in ClickHouse, renders dashboards. Never writes back. |

## Data Flow (Detailed)

### Request N (Pre-Promotion — Baseline)

```
Client → POST /api/query {prompt}

1. Orchestrator creates root span: evomind.request
2. Orchestrator → Rule Retriever
   → Span: evomind.rule.retrieval
   → Returns: [] (no Active rules)
3. Orchestrator → Guidance Injector (skipped — no rules)
4. Orchestrator → SQL Agent (prompt only)
   → Span: evomind.sql.generation
   → Returns: unsafe_sql (string interpolation)
5. Orchestrator → Outcome Evaluator
   → Span: evomind.sql.evaluation
   → Returns: EvaluationResult {classification="unsafe", reason="..."}
6. Orchestrator → Observation Factory
   → Span: evomind.observation.created
   → Returns: Observation
7. Orchestrator → Evidence Store
   → Span: evomind.evidence.appended
   → Returns: EvidenceRecord
8. Orchestrator → Confidence Engine
   → Span: evomind.confidence.updated
   → Returns: new_confidence (float)
9. Orchestrator → Rule Registry (check promotion)
   → Span: evomind.rule.state_change (conditional)
   → May transition Candidate → Active
10. Orchestrator returns Response to client
11. Orchestrator ends root span
```

### Request N+1 (Post-Promotion — Guided)

```
Same as above, except:

2. Rule Retriever → Returns: [rule_1] (Active rule)
3. Guidance Injector → Returns: modified_prompt with rule guidance
4. SQL Agent (with guidance) → Returns: safe_sql (parameterized)
5-9. Evidence is supporting → Confidence increases
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Developer Machine                  │
│                                                      │
│  ┌──────────────────┐   ┌─────────────────────────┐ │
│  │ EvoMind Service  │   │   SigNoz (Docker)       │ │
│  │                  │   │                         │ │
│  │ FastAPI :8000    │──▶│ OTel Collector :4317    │ │
│  │ SQLite :memory   │   │ ClickHouse              │ │
│  │ OTel SDK         │   │ Query Service           │ │
│  └──────────────────┘   │ Frontend :3301          │ │
│                         └─────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

SigNoz runs as a single Docker Compose stack. EvoMind runs as a standalone Python process. The OTel SDK exports spans to the SigNoz OTel Collector.

## Technology Choices

| Decision | Chosen | Alternatives | Rationale |
|---|---|---|---|
| Language | Python 3.11+ | TypeScript, Go | Best OTel SDK maturity. Standard for AI/ML tooling. Target audience expectation. |
| API framework | FastAPI | Flask, Django | Native async. Built-in OpenAPI. First-class OTel integration. Minimal boilerplate. |
| Storage | SQLite | PostgreSQL, Redis, in-memory | Zero setup. ACID. Sufficient for single-vertical-slice. File-based persistence without server. |
| SQL parser | sqlparse | Custom regex, AST libs | Deterministic. Mature. Handles multiple dialects. AST-level analysis without executing SQL. |
| Telemetry | OpenTelemetry | SigNoz API direct, Prometheus | Vendor-neutral. SigNoz is OTel-native. Single SDK for traces + metrics. No lock-in. |
| Agent | Mock deterministic | OpenAI, Anthropic, Claude | Zero cost, zero latency, fully reproducible. Demo must be scriptable. Real LLM can be swapped later. |
| Confidence model | Beta-Bernoulli | Thompson Sampling, Neural, Heuristic | Simplest fully-Bayesian model. Every parameter is interpretable. Closed-form update. |
