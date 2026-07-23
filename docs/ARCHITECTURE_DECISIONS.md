# EvoMind Observability — Architecture Decision Records

Each entry records a significant architectural decision, the alternatives considered, and the rationale for the choice.

---

## ADR-001: Programming Language — Python 3.11+

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Python 3.11+ |
| **Alternatives** | TypeScript, Go, Rust |

**Rationale:**
- OpenTelemetry Python SDK is mature and well-documented
- `sqlparse` provides deterministic SQL parsing without JVM or native dependencies
- Python is the lingua franca of AI/ML engineering — the target audience for this project
- FastAPI provides production-grade async HTTP with minimal boilerplate

**Tradeoff:** Python is slower than Go or Rust for high-throughput scenarios. This is acceptable because the hackathon handles one request at a time.

**Failure mode:** Python's GIL limits concurrency. Mitigated by FastAPI's async model and the single-threaded demo workload.

---

## ADR-002: Storage — SQLite

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | SQLite (via `sqlite3` stdlib) |
| **Alternatives** | PostgreSQL, Redis, in-memory dicts, JSON files |

**Rationale:**
- Zero external dependencies — no database server to install
- ACID compliance guarantees consistency across concurrent requests
- Single file — easy to reset between demo runs
- Sufficient for the single-vertical-slice scope (one rule, one agent)
- SQL triggers and constraints enforce data integrity

**Tradeoff:** SQLite does not scale to multiple writers. Acceptable for a single-process demo. PostgreSQL can replace SQLite in future work without changing the data access layer.

**Rejected — PostgreSQL:** Adds 5 minutes of setup time for every demo environment. Overkill for < 100 rows.

**Rejected — in-memory dicts:** No persistence across restarts. Cannot demonstrate the learning lifecycle persisting.

**Rejected — JSON files:** No query capability, no integrity constraints, no concurrent access.

---

## ADR-003: Confidence Model — Beta-Bernoulli

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Beta-Bernoulli conjugate model |
| **Alternatives** | Simple ratio, Thompson Sampling, heuristic weights, neural network |

**Rationale:**
- Every parameter is interpretable: α = supporting + prior, β = contradicting + prior
- Closed-form posterior update: O(1) per observation
- Confidence = α/(α+β) is a simple ratio an engineer can verify manually
- Bayesian foundation naturally handles uncertainty with few observations
- The prior Beta(1,1) encodes "no prior belief" without requiring domain expertise

**Tradeoff:** The model assumes independent and identically distributed observations, which is a simplification. Evidence from different contexts is treated equally. Acceptable for the single-domain scope.

**Rejected — Simple ratio (pass/total):** No principled uncertainty handling. Confidence would be 1.0 after 1 supporting observation with 0 contradictions.

**Rejected — Thompson Sampling:** Designed for multi-armed bandits with exploration. Adds stochasticity that harms reproducibility.

**Rejected — Neural network:** Completely opaque. Violates the explainability principle.

---

## ADR-004: SQL Safety Evaluator — Rule-Based, Deterministic

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | sqlparse-based AST analysis with pattern matching |
| **Alternatives** | LLM-as-judge, SQL execution against test DB, regex-only |

**Rationale:**
- Deterministic: same SQL → same classification, every time
- Zero latency: no network calls, no model inference
- Complete test coverage via input/output matrix
- Explainable: every classification has a specific, traceable pattern match
- The SQL text itself is the ground truth — no hidden state

**Tradeoff:** Cannot detect injection when the SQL text contains a legitimate constant vs. a user-supplied value (e.g., `WHERE status = 'active'`). This conservative bias (flagging as unsafe when uncertain) is intentional — it's better to over-flag than under-flag in a security context.

**Rejected — LLM-as-judge:** Non-deterministic, expensive, opaque. Contradicts "no meta-agent" principle.

**Rejected — SQL execution:** Requires a live database. Security risk. Cannot detect injection from execution result.

---

## ADR-005: Telemetry — OpenTelemetry (Not SigNoz API Direct)

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | OpenTelemetry SDK → OTLP exporter → SigNoz OTel Collector |
| **Alternatives** | Direct SigNoz API calls, Prometheus, custom logging |

**Rationale:**
- Vendor-neutral: can swap SigNoz for any OTel-compatible backend
- Single SDK for traces + metrics + logs
- SigNoz is built for OTel — OTLP is the first-class protocol
- Trace context propagation is automatic (trace_id, span_id)
- Rich span attributes enable structured querying in SigNoz

**Tradeoff:** OTel adds a dependency and configuration surface. Acceptable because OTel is the industry standard and the setup is one-time.

**Rejected — Direct SigNoz API calls:** Couples the system to SigNoz's proprietary API. Violates vendor-neutrality.

**Rejected — Prometheus only:** Metrics-only. Cannot capture trace hierarchy or span attributes.

---

## ADR-006: Agent — Mock (Deterministic) for Hackathon

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Mock deterministic agent with two modes |
| **Alternatives** | Real LLM (OpenAI, Anthropic, Claude), real open-source model |

**Rationale:**
- Zero cost, zero latency, zero API keys
- Fully reproducible demo: every run produces the same sequence
- The product is the *observability platform*, not the agent — the agent is the subject
- Mock agent isolates the observability system from LLM variability

**Failure mode:** A real LLM might not follow guidance 100% of the time. The mock agent always does. This means the demo shows an idealized learning curve. To address this: the mock agent has an "ignore guidance" mode for the regression scenario (Step 7 in the demo plan).

**Rejected — Real LLM:** Non-deterministic. Cost per demo run. API key management. Latency slows demo pace.

**Replaced — Open-source model (local):** Requires GPU or significant CPU resources. Setup complexity.

---

## ADR-007: Trace Structure — Flat Siblings Under Root Span

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Root span `evomind.request` with flat child spans (siblings) |
| **Alternatives** | Deeply nested spans mirroring call stack, single span with events |

**Rationale:**
- Flat structure makes every lifecycle step equally visible in the flamegraph
- No span is "hidden" inside a parent's collapsed view
- Easy to see duration of each step independently
- Easy to add new steps without restructuring

**Tradeoff:** The flamegraph shows all steps at the same depth, losing the call-stack hierarchy. This is acceptable because the lifecycle is strictly sequential — no parallel branches exist.

**Rejected — Deep nesting:** Would require restructuring every time a step is added. Hard to compare steps across requests.

**Rejected — Single span with events:** Events don't have duration, making it impossible to time individual steps.

---

## ADR-008: Pre-Seeded Behavioral Rule (Not Auto-Discovered)

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Single behavioral rule seeded at startup |
| **Alternatives** | Auto-discover rule from first observation, CLI-created rule |

**Rationale:**
- The product definition specifies exactly one behavioral rule
- Pre-seeding guarantees the rule exists before any request
- The rule's parameters (thresholds, guidance text) are visible in SigNoz from trace 0
- No code path for rule creation — reduces surface area

**Tradeoff:** The rule must be defined by the engineer, not discovered by the system. This is intentional — automatic pattern discovery is explicitly out of scope for this hackathon.

**Rejected — Auto-discovery:** Out of scope. Requires pattern mining, clustering, or LLM analysis.

---

## ADR-009: Evidence Type Derivation — Three-State Model

| Decision | Value |
|---|---|
| **Status** | Revised |
| **Chosen** | Context-dependent mapping: pre-promotion uses {supporting, baseline, neutral}; post-promotion uses {supporting, contradicting, neutral} |
| **Alternatives** | Single 2×3 table (original), LLM-as-judge, heuristic scoring |

**Rationale:**
- Safe SQL before rule promotion does NOT prove the rule is unnecessary — it only proves the agent already behaved correctly. Classifying it as "contradicting" was semantically wrong.
- The three-state model separates pre-promotion observations (which establish the need for the rule) from post-promotion observations (which validate the rule's effectiveness).
- Baseline observations are recorded for traceability but do not affect confidence, preserving the integrity of the Beta-Bernoulli model.
- The derivation remains fully deterministic: 2 tables × 3 classifications = 6 total states, each with a unique mapping.

**Tradeoff:** The factory now needs the rule's current status (not just whether guidance was injected). This adds a dependency on the RuleRegistry. Acceptable because the factory already receives the RequestContext which includes `rule_retrieved_id` for registry lookup.

**Rejected — Single table with "contradicting" for safe + no guidance:** Semantically incorrect. A safe result before the rule exists cannot contradict a rule that hasn't been tested.

---

## ADR-010: All Thresholds Configurable, Not Hardcoded

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | `promotion_threshold`, `demotion_threshold`, `min_evidence` as BehavioralRule fields (configurable) |
| **Alternatives** | Hardcoded constants, environment variables only |

**Rationale:**
- Thresholds are visible in SigNoz as rule attributes — an engineer inspecting a trace can see which thresholds were in effect
- Configuration is per-rule, enabling future multi-rule support without architectural change
- Defaults are set at rule creation time but can be overridden

**Tradeoff:** More configuration surface. Acceptable because the defaults are sensible and the thresholds only need setting once.

---

## ADR-011: No Real-Time Feedback Loop

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Post-hoc observability only (system → SigNoz, unidirectional) |
| **Alternatives** | SigNoz query → Orchestrator feedback, adaptive thresholds |

**Rationale:**
- The product is a *debugger*, not a *controller*
- SigNoz must never participate in the learning loop
- Write-only telemetry guarantees the observability layer cannot influence behavior
- An engineer viewing SigNoz may manually adjust parameters, but the automated system never consults SigNoz

**Rejected — Adaptive thresholds:** Would create a feedback loop between SigNoz and the learning system. Violates the "SigNoz never participates in learning" constraint.

---

## ADR-012: Single File for Mock Agent Prompt Mapping

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | A simple deterministic function: `prompt → "SELECT ... FROM ... WHERE ... = <literal>"` or `prompt → "SELECT ... FROM ... WHERE ... = ?"` |
| **Alternatives** | Full prompt-to-SQL mapping table, regex templates |

**Rationale:**
- The mock agent needs only two output modes (safe/unsafe)
- A real LLM would interpret the prompt; the mock skips interpretation and uses the prompt to construct a plausible SQL response
- Keeps the mock under 50 LOC

**Tradeoff:** The mock SQL doesn't perfectly match the prompt semantics. Acceptable because the audience is evaluating the observability system, not the SQL quality.

---

## ADR-013: SQL Evaluator Scope — Text Only

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Evaluator analyzes only generated SQL text via sqlparse AST |
| **Alternatives** | Python AST inspection, runtime taint tracking, DB driver hooking |

**Rationale:**
- The agent emits SQL text; evaluating that text is the simplest and most direct approach
- Python AST inspection would couple the evaluator to the agent's implementation language
- Runtime taint tracking requires execution, violates the "no execute" principle
- DB driver hooking requires a live database, adds security risk

**Frozen scope:** The evaluator does NOT inspect Python source, ORM queries, execution traces, or any non-SQL artifact. This scope is frozen for the hackathon.

---

## ADR-014: SQL Privacy via Masking Configuration

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Configurable `mask_sql` flag with truncation + SHA-256 hashing |
| **Alternatives** | Full SQL in all spans, never store SQL, regex redaction |

**Rationale:**
- Demo mode (`mask_sql = false`): full SQL is visible in spans for maximum debuggability
- Production mode (`mask_sql = true`): SQL is truncated and hashed to prevent sensitive data from entering SigNoz
- The hash enables cross-trace correlation (same SQL = same hash) without exposing content
- Full SQL remains accessible in local SQLite via `request.id` correlation

**Rejected — Never store SQL:** Makes debugging impossible. The whole point is to observe SQL behavior.

**Rejected — Regex redaction:** Too fragile. Cannot reliably detect PII in SQL without schema knowledge.

---

## ADR-015: Version Metadata on Every Trace

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Four version fields on root span: `app.version`, `schema.version`, `rule.version`, `telemetry.version` |
| **Alternatives** | Single version field, no versioning, git commit hash only |

**Rationale:**
- Multiple version fields isolate the source of changes: was the application updated? Was the rule definition changed? Was the telemetry model modified?
- Enables filtering traces by version in SigNoz dashboards
- Git commit hash alone does not capture schema or rule versions

**Tradeoff:** Four version fields add 4 attributes per trace. Acceptable — the cardinality is extremely low.

---

## ADR-016: Uniform Exception Instrumentation

| Decision | Value |
|---|---|
| **Status** | Accepted |
| **Chosen** | Every component catches exceptions, marks span ERROR, records exception event, reraises typed error; Orchestrator catches all at root span |
| **Alternatives** | Let exceptions propagate uncaught, catch only at Orchestrator, log-only error handling |

**Rationale:**
- Catching at component boundary ensures every error is attached to the correct span (the span where it occurred), not to the root span
- The `exception.escaped` attribute signals whether the Orchestrator should expect the error
- Trace continuity is preserved — even errored traces complete and are visible in SigNoz
- A totally uncaught exception would cause the trace to end abruptly with no `lifecycle.complete` span, making it hard to distinguish from a service crash

**Rejected — Catch only at Orchestrator:** Error would be attributed to the root span, losing the component context. Investigators would not know which component failed.

---
