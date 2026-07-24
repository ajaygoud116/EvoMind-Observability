# EvoMind Observability Guide

How to use SigNoz to investigate every behavioral change in the AI agent.

---

## Prerequisites

- SigNoz running at `http://localhost:3301`
- EvoMind running with `EVOMIND_OTEL_ENABLED=true` (default)
- At least one request processed (run `python demo.py --auto`)

---

## Overview Dashboard

Navigate to **Dashboard → EvoMind Overview**.

### Panel 1: Confidence Over Time

**What it shows:** A line chart of `evomind.rule.confidence` across all requests.

**How to read it:**
- Flat line at 0.50 → initial state, no evidence
- Rising line → evidence accumulating (supporting)
- Sharp inflection → state change occurred
- Plateau at current confidence → evidence accumulation rate has decreased

**Why it matters:** One glance tells the judge whether the system learned.

### Panel 2: SQL Safety Ratio

**What it shows:** A gauge/pie chart of `evomind.sql.safety.ratio`.

**How to read it:**
- 0.0 = all unsafe
- 1.0 = all safe
- Partial = mixed

**Why it matters:** Shows overall behavior improvement at a glance.

### Panel 3: Evidence Timeline

**What it shows:** Bar chart of supporting vs contradicting evidence per request.

**How to read it:**
- Green bars = supporting evidence (desired)
- Red bars = contradicting evidence (undesired)
- Pattern of green → red → green shows regression and recovery

### Panel 4: Recent Traces

**What it shows:** Table of the most recent traces with key attributes.

**How to read it:**
- Each row is one request
- Columns: trace_id, request_id, classification, rule_retrieved, confidence, timestamp
- Sort by timestamp to see progression

---

## Trace Investigation

### Finding a Trace

1. Go to **Traces** in the left sidebar
2. Filter by service name: `evomind-observability`
3. Sort by timestamp descending
4. Click any trace to open it

### Trace Anatomy

A complete trace has this structure:

```
evomind.request                              (root span)
├── evomind.rule.retrieval                   (found=true|false)
├── evomind.guidance.injection               (injected=true|false)
├── evomind.sql.generation                   (SQL string, length)
├── evomind.sql.evaluation                   (classification, patterns)
├── evomind.observation.created              (evidence_type)
├── evomind.evidence.appended                (delta)
├── evomind.confidence.updated               (before → after)
├── evomind.rule.state_change                 (only if status changed)
└── evomind.lifecycle.complete               (summary)
```

Compare early traces (few spans) with later traces (more spans after promotion).

### Key Span Attributes

#### `evomind.rule.retrieval`
| Attribute | Meaning | Example |
|-----------|---------|---------|
| `rule.retrieved` | Was a rule found? | `true` |
| `rule.id` | Retrieved rule UUID | `abc-123` |
| `rule.name` | Rule name | `use_parameterized_sql` |
| `rule.status` | Current status | `active` |
| `rule.confidence` | Confidence at retrieval time | `0.80` |
| `rules.found` | Number of active rules | `1` |

#### `evomind.guidance.injection`
| Attribute | Meaning | Example |
|-----------|---------|---------|
| `guidance.injected` | Was guidance prepended? | `true` |
| `prompt.length.original` | Original prompt length | `22` |
| `prompt.length.modified` | Modified prompt length | `152` |
| `guidance.length` | Guidance text length | `120` |

#### `evomind.sql.generation`
| Attribute | Meaning | Example |
|-----------|---------|---------|
| `app.sql.generated` | The actual SQL | `DELETE FROM users WHERE id = ?` |
| `app.sql.length` | SQL string length | `36` |
| `rule.retrieved` | Rule available? | `true` |
| `guidance.injected` | Guidance used? | `true` |

#### `evomind.sql.evaluation`
| Attribute | Meaning | Example |
|-----------|---------|---------|
| `classification` | safe/unsafe/ambiguous | `safe` |
| `evaluator.confidence` | Evaluator certainty | `1.0` |
| `detected.patterns` | Patterns found | `["delete_where"]` |

#### `evomind.observation.created`
| Attribute | Meaning | Example |
|-----------|---------|---------|
| `observation.evidence_type` | supporting/contradicting/baseline/neutral | `supporting` |
| `observation.classification` | Original classification | `safe` |

#### `evomind.confidence.updated`
| Attribute | Meaning | Example |
|-----------|---------|---------|
| `confidence.before` | Pre-update confidence | `0.80` |
| `confidence.after` | Post-update confidence | `0.83` |
| `confidence.delta` | Change | `0.03` |
| `alpha` | Alpha parameter | `6.0` |
| `beta` | Beta parameter | `2.0` |

#### `evomind.rule.state_change`
| Attribute | Meaning | Example |
|-----------|---------|---------|
| `from_status` | Previous status | `candidate` |
| `to_status` | New status | `active` |
| `reason` | Why the change happened | `Confidence 0.80 >= 0.75...` |
| `confidence` | Confidence at transition | `0.80` |

---

## Metrics

| Metric | Type | Where to See It |
|--------|------|-----------------|
| `evomind.requests.total` | Counter | Dashboard → Requests panel |
| `evomind.sql.safety.ratio` | ObservableGauge | Dashboard → Safety panel |
| `evomind.rule.confidence` | ObservableGauge | Dashboard → Confidence chart |
| `evomind.rule.evidence.count` | ObservableGauge | Dashboard → Evidence panel |

---

## Root Cause Investigation

### "Why did confidence increase?"

1. Open the trace for the request that caused the increase
2. Find the `evomind.confidence.updated` span
3. Read the `confidence.before` and `confidence.after` attributes
4. The span is preceded by `evomind.evidence.appended` — check the evidence type

### "Which evidence caused it?"

1. Go to the trace
2. Find `evomind.observation.created` span
3. Read `observation.evidence_type` (supporting increases α, contradicting increases β)
4. The observation contains the SQL that was classified

### "Which request caused promotion?"

1. Search for traces containing `evomind.rule.state_change` spans
2. Filter by service: `evomind-observability`
3. Open the trace — the promotion reason is in the state change span
4. The trace contains the exact SQL, classification, and confidence at promotion

### "Which SQL triggered the observation?"

1. Open the observation's parent trace
2. Find `evomind.sql.generation` span
3. Read `app.sql.generated` — the exact SQL string is there

### "Which trace recorded it?"

Every `evomind.observation.created` span has a `trace_id` accessible from the trace view. The response from the API includes `request_id` — you can find it in SigNoz by searching for the request_id attribute.

---

## The Three-State Evidence Semantics

The evidence type depends on rule status and classification:

### Pre-Promotion (rule is Candidate)
| Classification | Evidence Type | Effect |
|---------------|---------------|--------|
| unsafe | **supporting** | α += 1, confidence increases |
| safe | **baseline** | No change |
| ambiguous | **neutral** | No change |

### Post-Promotion (rule is Active — guidance injected)
| Classification | Evidence Type | Effect |
|---------------|---------------|--------|
| safe | **supporting** | α += 1, confidence increases |
| unsafe | **contradicting** | β += 1, confidence decreases |
| ambiguous | **neutral** | No change |

---

## Rules for Investigators

1. **Every decision is a span.** If you can't find it, it didn't happen.
2. **Every span has attributes.** The data is there — just click.
3. **Compare traces.** Before vs after promotion tells the full story.
4. **Follow the evidence.** Observation → Evidence → Confidence → State.
5. **Metrics tell the trend, traces tell the story.**
