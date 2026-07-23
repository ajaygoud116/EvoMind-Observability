# EvoMind Trace Walkthrough

This document shows the complete trace structure for a single request through the EvoMind learning lifecycle.

---

## Trace #1: Before Promotion (Candidate Rule)

When the rule is still a Candidate, the trace is simple — the rule is not retrieved, no guidance is injected.

### Visual Structure

```
evomind.request
├── evomind.rule.retrieval           # found=false, rules.found=0
├── evomind.sql.generation           # unsafe SQL with inline values
├── evomind.sql.evaluation           # classification=unsafe
├── evomind.observation.created      # evidence_type=supporting
├── evomind.evidence.appended        # delta=0.0
├── evomind.confidence.updated       # 0.50 → 0.67
└── evomind.lifecycle.complete
```

### Key Observations

- **No guidance injection span** — the rule was not active, so no injection occurred
- **SQL has inline values** — `SELECT * FROM users WHERE id = 5`
- **Evidence is `supporting`** — pre-promotion semantics: unsafe → supporting
- **Confidence increases** — supporting evidence adds α

### Full Attribute Dump

```
evomind.request
  app.version: 0.1.0
  schema.version: 1.1.0
  rule.version: 1.0.0
  telemetry.version: 1.1.0

evomind.rule.retrieval
  rule.retrieved: false
  rule.id: null
  rule.name: null
  rule.status: null
  rule.confidence: null
  rules.found: 0

evomind.sql.generation
  rule.retrieved: false
  rule.id: <seeded_rule_id>
  rule.name: use_parameterized_sql
  guidance.injected: false
  app.sql.generated: SELECT * FROM users WHERE id = 5
  app.sql.length: 34

evomind.sql.evaluation
  app.sql.length: 34
  sql.valid: true
  classification: unsafe
  evaluator.confidence: 1.0
  detected.patterns: ["inline_value"]

evomind.observation.created
  rule.id: <seeded_rule_id>
  request.id: <uuid>
  observation.id: <uuid>
  observation.evidence_type: supporting
  observation.classification: unsafe

evomind.evidence.appended
  rule.id: <seeded_rule_id>
  observation.id: <uuid>
  evidence_type: supporting
  evidence.id: <uuid>
  evidence.delta: 0.0

evomind.confidence.updated
  rule.id: <seeded_rule_id>
  confidence.before: 0.50
  confidence.after: 0.67
  confidence.delta: 0.17
  alpha: 2.0
  beta: 1.0

evomind.lifecycle.complete
  request.id: <uuid>
  classification: unsafe
  evidence_type: supporting
  rule_confidence: 0.67
  confidence_delta: 0.17
  status_changed: false
  to_status: candidate
```

---

## Trace #3: Promotion (Candidate → Active)

The third unsafe request has enough evidence (3+) and sufficient confidence (≥0.75) to promote the rule.

### Visual Structure

```
evomind.request
├── evomind.rule.retrieval           # found=false, rules.found=0
├── evomind.sql.generation           # unsafe SQL
├── evomind.sql.evaluation           # classification=unsafe
├── evomind.observation.created      # evidence_type=supporting
├── evomind.evidence.appended
├── evomind.confidence.updated       # 0.75 → 0.80
├── evomind.rule.state_change        # candidate → active  ← NEW!
└── evomind.lifecycle.complete
```

### What Changed

- **New span: `evomind.rule.state_change`**
  - `from_status`: `candidate`
  - `to_status`: `active`
  - `reason`: `Confidence 0.8000 >= 0.75 with 3 evidence (min 3)`

### Why This Matters

This is the **learning event**. Before this trace, the agent had no guidance. After this trace, every subsequent request will receive guidance. The behavior change starts here.

---

## Trace #4: First Guided Request (Active Rule)

After promotion, the rule is active. The next request triggers rule retrieval and guidance injection.

### Visual Structure

```
evomind.request
├── evomind.rule.retrieval           # found=true, confidence=0.80  ← CHANGED
├── evomind.guidance.injection       # injected=true                ← NEW
├── evomind.sql.generation           # SAFE SQL with ? placeholders ← CHANGED
├── evomind.sql.evaluation           # classification=safe          ← CHANGED
├── evomind.observation.created      # evidence_type=supporting (post-promotion)
├── evomind.evidence.appended
├── evomind.confidence.updated       # 0.80 → 0.83
└── evomind.lifecycle.complete
```

### Key Changes vs Trace #1

| Aspect | Trace #1 | Trace #4 |
|--------|----------|----------|
| Rule Retrieved | false | **true** |
| Guidance Injected | (no span) | **true** |
| SQL | `WHERE id = 5` | **`WHERE id = ?`** |
| Classification | unsafe | **safe** |
| Evidence Type | supporting | **supporting** (different semantics) |

### The Guidance Injection Span

The `evomind.guidance.injection` span contains:
```
guidance.injected: true
prompt.length.original: 22
prompt.length.modified: 152
guidance.length: 120
```

The guidance text is: `"IMPORTANT: Always use parameterized queries instead of string interpolation. Use ? placeholders for all values."`

### The SQL Generation Span

Before: `DELETE FROM users WHERE id = 1` (inline value — unsafe)  
After: `DELETE FROM users WHERE id = ?` (parameterized — safe)

---

## Trace #6: Converged State

After several safe requests, the system has converged.

### Visual Structure

Same as Trace #4, but:

- `guidance.injection` → `injected=true`
- `evomind.sql.evaluation` → `classification=safe`
- `evomind.confidence.updated` → `0.86 → 0.88`

### Full Confidence Evolution

| Request | Confidence | Status | SQL Safety |
|---------|-----------|--------|------------|
| 1 | 0.50 → 0.67 | candidate | unsafe |
| 2 | 0.67 → 0.75 | candidate | unsafe |
| 3 | 0.75 → **0.80** | **candidate → active** | unsafe |
| 4 | 0.80 → 0.83 | active | **safe** |
| 5 | 0.83 → 0.86 | active | safe |
| 6 | 0.86 → 0.88 | active | safe |

---

## How to Navigate in SigNoz

1. **Open a trace**: Traces → click any trace ID
2. **Expand spans**: Click each span to see its attributes
3. **Compare traces**: Use the "Compare" feature to see before/after
4. **Filter**: Use `evomind.rule.state_change` to find promotion events
5. **Search by attribute**: Search `classification = safe` to find guided requests
