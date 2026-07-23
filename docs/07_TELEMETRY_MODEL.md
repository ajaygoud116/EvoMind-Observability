# EvoMind Observability — Telemetry Model

## Guiding Principles

1. **Every lifecycle step is a span.** If a transition happens, it has a span. No silent state changes.
2. **Spans carry structured attributes, not just messages.** Every numeric value, identifier, and classification is a typed attribute, not embedded in a log line.
3. **Correlation is by trace_id.** One request = one trace. The trace_id flows through every span and is stored in the RequestContext for cross-referencing.
4. **Metrics aggregate; traces investigate.** Metrics show trends (confidence over time, safety ratio). Traces show individual request lifecycles.
5. **No PII in telemetry attributes.** SQL text is included only as a span attribute (not in logs/metrics) for debugging. Full SQL is not stored in SigNoz if it contains sensitive data — configurable via a `mask_sql` flag.
6. **Version everything.** Every trace carries application, schema, rule, and telemetry model version metadata to enable cross-deployment debugging and schema evolution tracking.

---

## Trace Hierarchy

One trace per request lifecycle. There is also a **startup trace** emitted when the application initializes.

### Startup Trace (emitted once at application start)

```
evomind.system.startup                                   [ROOT SPAN]
  └── evomind.rule.created                               [CHILD]
```

### Request Trace (emitted per request)

```
evomind.request                                         [ROOT SPAN]
  ├── evomind.rule.retrieval                            [CHILD]
  ├── evomind.guidance.injection                        [CHILD]  (conditional: only if rule retrieved)
  ├── evomind.sql.generation                            [CHILD]
  ├── evomind.sql.evaluation                            [CHILD]
  ├── evomind.observation.created                        [CHILD]
  ├── evomind.evidence.appended                         [CHILD]
  ├── evomind.confidence.updated                        [CHILD]
  ├── evomind.rule.state_change                         [CHILD]  (conditional: only if status changes)
  └── evomind.lifecycle.complete                         [CHILD]  (final summary)
```

All child spans are siblings (sequential, not nested). The root span covers the full request duration.

---

## Span Specifications

### Span: `evomind.request` (Root)

| Property | Value |
|---|---|
| Kind | `SERVER` |
| Status | `OK` on success, `ERROR` on internal failure |

**Attributes:**

| Attribute | Type | Example | Description |
|---|---|---|---|
| `app.name` | string | `evomind-observability` | Application identifier |
| `app.version` | string | `0.1.0` | Application version |
| `schema.version` | string | `1.1.0` | Data model schema version |
| `rule.version` | string | `1.0.0` | Behavioral rule definition version |
| `telemetry.version` | string | `1.1.0` | Telemetry model version |
| `request.id` | string | `req-0001` | Internal request ID (UUID) |
| `request.prompt` | string | `"Show me users with id 123"` | The natural language prompt (truncated to 1024 chars) |
| `rule.status` | string | `candidate` | Rule status at request time |
| `rule.retrieved` | bool | `false` | Whether any rule was retrieved |
| `rule.id` | string | `a1b2c3d4-0001` | Retrieved rule ID (empty if none) |
| `rule.name` | string | `use_parameterized_sql` | Retrieved rule name |
| `lifecycle.duration_ms` | int | `145` | Total request duration |

---

### Span: `evomind.rule.retrieval`

| Property | Value |
|---|---|
| Kind | `INTERNAL` |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `rule.retrieved` | bool | `false` |
| `rule.found_count` | int | `0` |
| `rule.id` | string | `a1b2c3d4-0001` (empty if none) |
| `rule.name` | string | `use_parameterized_sql` |
| `rule.status` | string | `candidate` |
| `rule.confidence` | float | `0.67` |
| `retrieval.reason` | string | `no_active_rules` / `rule_found_and_active` |

---

### Span: `evomind.guidance.injection`

Only created if `rule.retrieved == true`.

| Property | Value |
|---|---|
| Kind | `INTERNAL` |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `rule.id` | string | `a1b2c3d4-0001` |
| `rule.name` | string | `use_parameterized_sql` |
| `guidance.injected` | bool | `true` |
| `guidance.text` | string | `"IMPORTANT: Always use..."` (truncated to 512 chars) |
| `guidance.original_prompt_length` | int | `85` |
| `guidance.modified_prompt_length` | int | `215` |

---

### Span: `evomind.sql.generation`

| Property | Value |
|---|---|
| Kind | `INTERNAL` |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `sql.generated` | string | `"SELECT * FROM users WHERE id = 123"` (truncated to 2048 chars) |
| `sql.length` | int | `38` |
| `sql.has_placeholder` | bool | `false` |
| `sql.placeholder_type` | string | `""` (or `?`, `%s`, `$1`, etc.) |
| `agent.guidance_received` | bool | `false` |

---

### Span: `evomind.sql.evaluation`

| Property | Value |
|---|---|
| Kind | `INTERNAL` |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `evaluation.classification` | string | `unsafe` |
| `evaluation.reason` | string | `"Literal numeric value found in WHERE clause"` |
| `evaluation.detected_patterns` | string[] | `["literal_in_where:id"]` |
| `evaluation.confidence` | float | `1.0` (deterministic) |

---

### Span: `evomind.observation.created`

| Property | Value |
|---|---|
| Kind | `INTERNAL` |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `observation.id` | string | `obs-0001` |
| `observation.rule_id` | string | `a1b2c3d4-0001` |
| `observation.classification` | string | `unsafe` |
| `observation.evidence_type` | string | `supporting` |

---

### Span: `evomind.evidence.appended`

| Property | Value |
|---|---|
| Kind | `INTERNAL` |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `evidence.id` | string | `ev-0001` |
| `evidence.rule_id` | string | `a1b2c3d4-0001` |
| `evidence.type` | string | `supporting` |
| `evidence.request_id` | string | `req-0001` |
| `evidence.supporting_count` | int | `1` |
| `evidence.contradicting_count` | int | `0` |

---

### Span: `evomind.confidence.updated`

| Property | Value |
|---|---|
| Kind | `INTERNAL` |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `rule.id` | string | `a1b2c3d4-0001` |
| `rule.name` | string | `use_parameterized_sql` |
| `rule.confidence.before` | float | `0.50` |
| `rule.confidence.after` | float | `0.67` |
| `rule.confidence.delta` | float | `0.17` |
| `rule.alpha` | float | `2.0` |
| `rule.beta` | float | `1.0` |
| `evidence.type` | string | `supporting` |

---

### Span: `evomind.rule.state_change` (Conditional)

Only created when a rule transitions between states.

| Property | Value |
|---|---|
| Kind | `INTERNAL` |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `rule.id` | string | `a1b2c3d4-0001` |
| `rule.name` | string | `use_parameterized_sql` |
| `rule.status.from` | string | `candidate` |
| `rule.status.to` | string | `active` |
| `rule.confidence` | float | `0.80` |
| `transition.reason` | string | `confidence_threshold_met` |

---

### Span: `evomind.lifecycle.complete` (Final Summary)

Created as the last span before the root span ends. Provides a single-span summary of the full lifecycle for quick scanning.

| Attribute | Type | Example |
|---|---|---|
| `summary.sql_safe` | bool | `false` |
| `summary.rule_retrieved` | bool | `false` |
| `summary.guidance_injected` | bool | `false` |
| `summary.confidence_delta` | float | `0.17` |
| `summary.state_changed` | bool | `false` |

---

### Span: `evomind.rule.created` (Startup — not per-request)

Emitted once when the application starts and the behavioral rule is seeded into the registry. This is a child of the `evomind.system.startup` root span, NOT a child of `evomind.request`.

| Property | Value |
|---|---|
| Kind | `INTERNAL` |
| When | Application startup, once |

**Attributes:**

| Attribute | Type | Example |
|---|---|---|
| `rule.id` | string | `a1b2c3d4-0001` |
| `rule.name` | string | `use_parameterized_sql` |
| `rule.status.initial` | string | `candidate` |
| `rule.confidence.initial` | float | `0.50` |
| `rule.alpha.initial` | float | `1.0` |
| `rule.beta.initial` | float | `1.0` |
| `threshold.promotion` | float | `0.75` |
| `threshold.demotion` | float | `0.35` |
| `threshold.min_evidence` | int | `3` |

**Why it exists:** This span anchors the rule's lifecycle in time. Every trace's `rule.retrieved` or `rule.state_change` can be traced back to this creation event. Without it, the rule's existence has no observable beginning — the first request trace would show a rule that "already exists" with no creation context. This span makes the full lifecycle observable from creation through promotion to (potentially) suspension.

---

## Span Events

Span events capture high-cardinality or infrequent details that don't belong as span attributes.

### Event: `evomind.evaluation.details`

Emitted on the `evomind.sql.evaluation` span when classification is `unsafe`.

| Attribute | Type | Example |
|---|---|---|
| `sql.full` | string | Full SQL (untruncated) |
| `evaluation.detailed_reason` | string | Extended explanation |
| `evaluation.token_context` | string | Relevant token subtree from sqlparse |

### Event: `evomind.state.snapshot`

Emitted on the root span after each lifecycle completes. Captures the full system state at that instant.

| Attribute | Type | Example |
|---|---|---|
| `rule.id` | string | `a1b2c3d4-0001` |
| `rule.status` | string | `active` |
| `rule.confidence` | float | `0.80` |
| `rule.supporting_count` | int | `3` |
| `rule.contradicting_count` | int | `0` |
| `rule.total_observations` | int | `3` |

---

## Exception Instrumentation Policy

Every component must follow a uniform exception handling and telemetry policy.

### Policy

1. **Every expected exception** is caught at the component boundary
2. The component's span is set to `status = ERROR`
3. An `exception` span event is recorded with structured attributes
4. The exception is re-raised as a typed `EvoMindError` subclass
5. The Orchestrator catches all `EvoMindError` exceptions at the root span level
6. Trace continuity is preserved — the trace is not abandoned, it completes with error status

### Exception Span Event Attributes

| Attribute | Type | Required | Example |
|---|---|---|---|
| `exception.type` | string | yes | `EvaluationError` |
| `exception.message` | string | yes | `sqlparse failed to parse input` |
| `exception.stacktrace` | string | no | (multi-line, configurable) |
| `exception.escaped` | bool | yes | `true` if re-raised beyond the component |

### Exception-to-Span Mapping

| Component | Expected Exceptions | Span That Records It |
|---|---|---|
| SQL Agent | `AgentGenerationError`, `ValueError` | `evomind.sql.generation` |
| Outcome Evaluator | `EvaluationError`, `ValueError` | `evomind.sql.evaluation` |
| Observation Factory | `ObservationError`, `ValueError` | `evomind.observation.created` |
| Evidence Store | `EvidenceStoreError` | `evomind.evidence.appended` |
| Confidence Engine | `ConfidenceError`, `KeyError` | `evomind.confidence.updated` |
| Rule Registry | `RegistryError`, `KeyError` | `evomind.rule.state_change` |
| Rule Retriever | `RetrievalError` | `evomind.rule.retrieval` |
| Guidance Injector | `InjectionError` | `evomind.guidance.injection` |
| Orchestrator | `EvoMindError` (catch-all) | `evomind.request` (root span) |

### Error Flow

```
Component raises Exception
  → Component catches, sets span.ERROR, records exception event
  → Reraises typed error
  → Orchestrator catches, sets root span.ERROR
  → Root span ends with error status
  → API returns 500 with error details
```

---

## Version Metadata

All traces carry version metadata to enable cross-deployment debugging and schema evolution tracking.

### Version Fields

| Field | Scope | Increment When | Example |
|---|---|---|---|
| `app.version` | Every trace | Application code changes | `0.1.0` |
| `schema.version` | Every trace | Data model changes (DDL) | `1.1.0` |
| `rule.version` | `evomind.rule.created` | Rule definition changes | `1.0.0` |
| `telemetry.version` | Every trace | Telemetry model changes | `1.1.0` |

### Why Versioning Matters

| Reason | Explanation |
|---|---|
| **Schema evolution** | When the data model changes (e.g., a new evidence type is added), old traces remain interpretable because their schema version is known. A dashboard can filter traces by `schema.version` to compare behavior across versions. |
| **Cross-deployment debugging** | If traces from different versions of the application co-exist in SigNoz (e.g., during a rolling deploy), engineers can distinguish which version produced each trace. |
| **Migration tracking** | When the rule definition or telemetry model is updated, the version field shows exactly when the change took effect. |
| **Long-term observability** | The product is a debugger for learning lifecycles that may span days or weeks. Versioning ensures that traces from different software versions remain comparable. |

---

## Metrics

Metrics are emitted every request. They aggregate across all traces.

### Metric: `evomind.requests.total`

| Property | Value |
|---|---|
| Type | Counter |
| Unit | requests |
| Description | Total requests received |

**Attributes:** none

### Metric: `evomind.sql.safety.ratio`

| Property | Value |
|---|---|
| Type | Gauge |
| Unit | ratio |
| Description | Rolling ratio of safe / (safe + unsafe) classifications in the current window |

**Attributes:**
| Attribute | Type | Example |
|---|---|---|
| `window_size` | int | `10` (configurable) |

### Metric: `evomind.rule.confidence`

| Property | Value |
|---|---|
| Type | Gauge |
| Unit | score |
| Description | Current confidence score for each behavioral rule |

**Attributes:**
| Attribute | Type | Example |
|---|---|---|
| `rule.id` | string | `a1b2c3d4-0001` |
| `rule.name` | string | `use_parameterized_sql` |

### Metric: `evomind.rule.evidence.count`

| Property | Value |
|---|---|
| Type | Gauge |
| Unit | count |
| Description | Total evidence count per rule, split by type |

**Attributes:**
| Attribute | Type | Example |
|---|---|---|
| `rule.id` | string | `a1b2c3d4-0001` |
| `evidence.type` | string | `supporting` / `contradicting` |

---

## Correlation ID Strategy

Every request receives a **request_id** (UUID v4) assigned by the Orchestrator. This ID is:

1. Stored in `RequestContext.id` in SQLite
2. Set as a span attribute on every span in the trace
3. Included in the response headers as `X-EvoMind-Request-Id`

The OTel `trace_id` is automatically generated by the OpenTelemetry SDK and linked to the `request_id` via span attributes. An engineer can:

- Start from SigNoz trace view → find `request.id` attribute
- Use `request.id` to query SQLite for full details
- Cross-reference between SigNoz and local storage

---

## Sampling Strategy

| Signal | Sampling | Rationale |
|---|---|---|
| Traces | `AlwaysOn` (sample 100%) | Low volume (demo). Every trace is potentially investigatable. |
| Metrics | Aggregated at source | No sampling. Metrics are counters/gauge. |
| Logs | `WARNING`+ only | Debug logs should use Python logging, not OTel. Only warnings and errors go to SigNoz logs. |

For production (future), a `ParentBased(head-based)` sampler with configurable ratio should be added.

---

## Retention

SigNoz default retention is used:
- Traces: 30 days
- Metrics: 30 days

SQLite records (observations, evidence, request contexts) are retained indefinitely for the demo.

---

## OpenTelemetry SDK Configuration

```python
# Conceptual configuration — not implementation
resource = Resource(attributes={
    "service.name": "evomind-observability",
    "service.version": "0.1.0",
    "deployment.environment": "development",
})

trace_exporter = OTLPSpanExporter(
    endpoint="http://localhost:4317",  # SigNoz OTel Collector
    insecure=True,
)

metric_exporter = OTLPMetricExporter(
    endpoint="http://localhost:4317",
    insecure=True,
)

provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(trace_exporter)
provider.add_span_processor(processor)
```

---

## Why Each Signal Exists

| Span | Why it is a span (not a log or metric) |
|---|---|---|
| `evomind.request` | Root span. Provides timing and overall status for the request. |
| `evomind.rule.created` | Startup-only. Marks the beginning of the rule's observable lifecycle. Only created once; too infrequent for a metric, too structured for a log. |
| `evomind.rule.retrieval` | A discrete operation with a clear start/end. Its result determines the rest of the flow. |
| `evomind.guidance.injection` | A state mutation (prompt modification). Needs duration tracking if it grows complex. |
| `evomind.sql.generation` | The core agent operation. Duration is important. |
| `evomind.sql.evaluation` | A decision point. The classification determines the evidence direction. |
| `evomind.observation.created` | A data creation event. Span captures the structured observation. |
| `evomind.evidence.appended` | A persistence operation. Links observation to rule. |
| `evomind.confidence.updated` | A computation. Before/after values are critical for debugging. |
| `evomind.rule.state_change` | A state machine transition. Only created when status changes (rare). |

| Metric | Why it is a metric (not a span or log) |
|---|---|
| `evomind.requests.total` | Aggregation across requests. A span is per-request. |
| `evomind.sql.safety.ratio` | Trend over time. Cannot be derived from individual spans without aggregation. |
| `evomind.rule.confidence` | A continuous value that changes across requests. A gauge captures the current value. |

| Span Event | Why it is an event (not a span or attribute) |
|---|---|
| `evomind.evaluation.details` | High-cardinality details that would bloat span attributes. |
| `evomind.state.snapshot` | A point-in-time annotation on the root span, equivalent to a log line but correlated in trace context. |
