# EvoMind Observability — Data Model

## Entity-Relationship Overview

```
RequestContext
     │ 1
     │
     ├──< 0..N Observations
     │
     └──< 0..N EvidenceRecords
               │
               └──> 1 BehavioralRule
                        │
                        └── 0..N LearningState (snapshots over time)
```

Every request produces exactly one RequestContext. For each request, if a behavioral rule exists, zero or one Observation is created, zero or one EvidenceRecord is appended, and zero or one Confidence update occurs.

---

## Entity: BehavioralRule

A behavioral rule is a prescriptive statement that, when confidence is sufficient, is injected as guidance to improve agent behavior.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID (v4) | PK, immutable | Stable identifier, appears in all spans |
| `name` | TEXT | NOT NULL, UNIQUE | Human-readable name, e.g. "use_parameterized_sql" |
| `description` | TEXT | | Longer explanation of the rule |
| `guidance_text` | TEXT | NOT NULL | The exact text injected into the prompt |
| `condition` | TEXT | JSON, nullable | Optional context conditions for retrieval (future use) |
| `status` | TEXT | NOT NULL, DEFAULT 'candidate' | One of: candidate, active, suspended, archived |
| `confidence` | REAL | NOT NULL, DEFAULT 0.5 | Current confidence: α / (α + β) |
| `alpha` | REAL | NOT NULL, DEFAULT 1.0 | Beta posterior α (supporting pseudocounts) |
| `beta` | REAL | NOT NULL, DEFAULT 1.0 | Beta posterior β (contradicting pseudocounts) |
| `promotion_threshold` | REAL | NOT NULL, DEFAULT 0.75 | Confidence above which status → active |
| `demotion_threshold` | REAL | NOT NULL, DEFAULT 0.35 | Confidence below which status → suspended |
| `min_evidence` | INTEGER | NOT NULL, DEFAULT 3 | Minimum total observations before promotion allowed |
| `supporting_count` | INTEGER | NOT NULL, DEFAULT 0 | Total supporting evidence records |
| `contradicting_count` | INTEGER | NOT NULL, DEFAULT 0 | Total contradicting evidence records |
| `created_at` | TEXT (ISO 8601) | NOT NULL | Rule creation timestamp |
| `updated_at` | TEXT (ISO 8601) | NOT NULL | Last modification timestamp |
| `promoted_at` | TEXT (ISO 8601) | Nullable | Timestamp of last Candidate → Active transition |
| `demoted_at` | TEXT (ISO 8601) | Nullable | Timestamp of last Active → Suspended transition |

### Constraints

- `CHECK (confidence BETWEEN 0.0 AND 1.0)`
- `CHECK (alpha > 0.0 AND beta > 0.0)`
- `CHECK (promotion_threshold > demotion_threshold)`
- `CHECK (min_evidence >= 1)`

---

## Entity: Observation

An observation is a single evaluation of an agent's output against a behavioral rule.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID (v4) | PK, immutable | Stable identifier |
| `request_id` | UUID (v4) | FK → RequestContext.id, NOT NULL | Links back to the request |
| `rule_id` | UUID (v4) | FK → BehavioralRule.id, NOT NULL | Which rule this observation pertains to |
| `classification` | TEXT | NOT NULL | One of: safe, unsafe, ambiguous |
| `evidence_type` | TEXT | NOT NULL | One of: supporting, contradicting, baseline, neutral |
| `sql_generated` | TEXT | Nullable | The SQL that was evaluated |
| `evaluation_reason` | TEXT | Nullable | Human-readable reason for classification |
| `metadata` | TEXT | JSON, nullable | Extensible key-value data |
| `created_at` | TEXT (ISO 8601) | NOT NULL | Observation timestamp |

### Evidence Type Derivation

The derivation depends on whether the rule was **active** (post-promotion, guidance injected) or **candidate** (pre-promotion, no guidance).

#### Pre-Promotion (rule status = candidate, no guidance injected)

| Classification | Evidence Type | Confidence Impact |
|---|---|---|
| safe | baseline | No update |
| unsafe | supporting | α += 1 |
| ambiguous | neutral | No update |

#### Post-Promotion (rule status = active, guidance injected)

| Classification | Evidence Type | Confidence Impact |
|---|---|---|
| safe | supporting | α += 1 |
| unsafe | contradicting | β += 1 |
| ambiguous | neutral | No update |

**Key semantic distinction:** A safe result before the rule is injected does NOT prove the rule is unnecessary — it only proves the agent already behaved correctly. "Baseline" records this fact without affecting confidence. After the rule is active, safe results confirm the rule is effective and increase confidence. Unsafe results after activation indicate the rule failed and decrease confidence.

---

## Entity: EvidenceRecord

An evidence record is the persisted link between an observation and a rule's evidence log. It exists as a separate entity to allow time-series querying independent of the observation detail.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID (v4) | PK, immutable | Stable identifier |
| `observation_id` | UUID (v4) | FK → Observation.id, NOT NULL | Source observation |
| `rule_id` | UUID (v4) | FK → BehavioralRule.id, NOT NULL | Target rule |
| `evidence_type` | TEXT | NOT NULL | supporting, contradicting, baseline, neutral |
| `request_id` | UUID (v4) | FK → RequestContext.id, NOT NULL | Links to request |
| `confidence_before` | REAL | NOT NULL | Rule confidence before this evidence |
| `confidence_after` | REAL | NOT NULL | Rule confidence after this evidence |
| `delta` | REAL | NOT NULL | confidence_after - confidence_before |
| `created_at` | TEXT (ISO 8601) | NOT NULL | Record timestamp |

---

## Entity: EvaluationResult

An evaluation result is a transient value object (not persisted independently — embedded in Observation).

| Field | Type | Constraints | Description |
|---|---|---|---|
| `classification` | TEXT | One of: safe, unsafe, ambiguous |
| `reason` | TEXT | Human-readable classification explanation |
| `detected_patterns` | TEXT[] | List of patterns found (e.g. ["f_string", "literal_in_where"]) |
| `confidence` | REAL | Evaluator's own certainty (1.0 for deterministic rules) |

---

## Entity: RequestContext

Captures the full context of a single request lifecycle.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID (v4) | PK, immutable | Correlates with OTel trace_id |
| `prompt` | TEXT | NOT NULL | The natural-language request |
| `sql_generated` | TEXT | Nullable | The SQL the agent produced |
| `guidance_injected` | TEXT | Nullable | Guidance text that was injected (if any) |
| `rule_retrieved_id` | UUID (v4) | FK → BehavioralRule.id, nullable | Rule retrieved (if any) |
| `rule_retrieved` | BOOLEAN | NOT NULL, DEFAULT false | Whether any rule was found |
| `classification` | TEXT | Nullable | Evaluation result |
| `trace_id` | TEXT | Nullable | OTel trace ID for SigNoz correlation |
| `created_at` | TEXT (ISO 8601) | NOT NULL | Request timestamp |

---

## Entity: LearningState (Snapshot)

A point-in-time snapshot of the learning system state. Emitted as a span event at the end of each request.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID (v4) | PK |
| `request_id` | UUID (v4) | FK → RequestContext.id |
| `rule_id` | UUID (v4) | FK → BehavioralRule.id |
| `confidence` | REAL | |
| `status` | TEXT | |
| `supporting_count` | INTEGER | |
| `contradicting_count` | INTEGER | |
| `total_evidence` | INTEGER | |
| `snapshot_at` | TEXT (ISO 8601) | |

Not stored in the main SQLite — emitted directly as a telemetry event.

---

## SQLite Schema

```sql
CREATE TABLE behavioral_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    guidance_text TEXT NOT NULL,
    condition TEXT,
    status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'active', 'suspended', 'archived')),
    confidence REAL NOT NULL DEFAULT 0.5
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    alpha REAL NOT NULL DEFAULT 1.0 CHECK (alpha > 0.0),
    beta REAL NOT NULL DEFAULT 1.0 CHECK (beta > 0.0),
    promotion_threshold REAL NOT NULL DEFAULT 0.75,
    demotion_threshold REAL NOT NULL DEFAULT 0.35,
    min_evidence INTEGER NOT NULL DEFAULT 3,
    supporting_count INTEGER NOT NULL DEFAULT 0,
    contradicting_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    promoted_at TEXT,
    demoted_at TEXT
);

CREATE TABLE observations (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES request_contexts(id),
    rule_id TEXT NOT NULL REFERENCES behavioral_rules(id),
    classification TEXT NOT NULL
        CHECK (classification IN ('safe', 'unsafe', 'ambiguous')),
    evidence_type TEXT NOT NULL
        CHECK (evidence_type IN ('supporting', 'contradicting', 'baseline', 'neutral')),
    sql_generated TEXT,
    evaluation_reason TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE evidence_records (
    id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES observations(id),
    rule_id TEXT NOT NULL REFERENCES behavioral_rules(id),
    evidence_type TEXT NOT NULL
        CHECK (evidence_type IN ('supporting', 'contradicting', 'baseline', 'neutral')),
    request_id TEXT NOT NULL REFERENCES request_contexts(id),
    confidence_before REAL NOT NULL,
    confidence_after REAL NOT NULL,
    delta REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE request_contexts (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    sql_generated TEXT,
    guidance_injected TEXT,
    rule_retrieved_id TEXT REFERENCES behavioral_rules(id),
    rule_retrieved BOOLEAN NOT NULL DEFAULT 0,
    classification TEXT,
    trace_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_observations_rule_id ON observations(rule_id);
CREATE INDEX idx_observations_request_id ON observations(request_id);
CREATE INDEX idx_evidence_records_rule_id ON evidence_records(rule_id);
CREATE INDEX idx_evidence_records_created_at ON evidence_records(created_at);
CREATE INDEX idx_request_contexts_created_at ON request_contexts(created_at);
```

## Relationships Diagram (Text)

```
RequestContext  1──N──> Observation  1──1──> EvidenceRecord
                                                   │
                                                   N
                                                   │
                                              BehavioralRule
                                                   │
                                                   1
                                                   │
                                              LearningState (in-memory, telemetry-only)
```

## Example Instances

### BehavioralRule (seeded)

```
id:           "a1b2c3d4-...-0001"
name:         "use_parameterized_sql"
guidance_text: "IMPORTANT: Always use parameterized queries with ? placeholders for all user-supplied values. Never use string interpolation or f-strings."
status:       "candidate"
confidence:   0.50
alpha:        1.0
beta:         1.0
```

### Observation (first unsafe request)

```
id:               "obs-0001"
request_id:       "req-0001"
rule_id:          "a1b2c3d4-...-0001"
classification:   "unsafe"
evidence_type:    "supporting"
sql_generated:    "SELECT * FROM users WHERE id = 123"
evaluation_reason: "Literal numeric value found in WHERE clause; no placeholder used"
```

### EvidenceRecord (after promotion)

```
id:                   "ev-0004"
observation_id:       "obs-0004"
rule_id:              "a1b2c3d4-...-0001"
evidence_type:        "supporting"
request_id:           "req-0004"
confidence_before:    0.80
confidence_after:     0.83
delta:                +0.03
```
