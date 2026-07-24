# EvoMind Observability

**An observability-first behavioral learning system for AI agents.**

EvoMind Observability is a hackathon project that demonstrates how to make an AI agent's behavioral changes **fully observable, auditable, and explainable** using OpenTelemetry traces and metrics, visualized through SigNoz.

A judge can answer every question about why an AI agent changed its behavior — without reading source code.

---

## The Problem

AI agents generate SQL. Sometimes safely (parameterized queries). Sometimes unsafely (string interpolation — SQL injection risk).

When an agent changes from unsafe to safe SQL, **why did it happen?**

- Was a behavioral rule applied?
- Was guidance injected?
- What evidence accumulated?
- How did confidence grow?
- Which trace recorded the change?

Without observability, these questions require reading source code or guessing. **EvoMind makes every decision visible.**

---

## The Solution

EvoMind wraps a SQL-generation agent with a **behavioral learning loop**:

1. **Observe** — classify generated SQL as safe or unsafe
2. **Learn** — accumulate evidence, update Beta-Bernoulli confidence
3. **Promote** — rules become active at confidence ≥ 0.75 with 3+ evidence
4. **Retrieve** — active rules are retrieved on subsequent requests
5. **Inject** — guidance ("always use parameterized queries") is injected
6. **Improve** — agent generates safer SQL, confidence grows

Every step emits **OpenTelemetry spans and metrics** — visible in SigNoz.

---

## Architecture (30 Seconds)

```
User Prompt
    │
    ▼
┌──────────────┐     ┌──────────────────┐
│ RuleRetriever│────▶│ GuidanceInjector │
└──────────────┘     └──────────────────┘
                           │
                           ▼
┌──────────────┐     ┌──────────────────┐
│  SQL Agent   │────▶│ SafetyEvaluator  │
└──────────────┘     └──────────────────┘
                           │
                           ▼
┌──────────────┐     ┌──────────────────┐
│ObservFactory │────▶│  EvidenceStore   │
└──────────────┘     └──────────────────┘
                           │
                           ▼
┌──────────────┐     ┌──────────────────┐
│ConfEngine    │────▶│  LearningState   │
└──────────────┘     └──────────────────┘
                           │
                           ▼
                   ┌──────────────┐
                   │   SigNoz     │  ← Traces + Metrics
                   └──────────────┘
```

Every arrow emits an OpenTelemetry span. Metrics are emitted at request, evidence, and confidence update points.

---

## The Learning Lifecycle

| Step | What Happens | SigNoz View |
|------|-------------|-------------|
| 1–3 | Agent generates unsafe SQL → supporting evidence → confidence rises | Confidence gauge: 0.50 → 0.80 |
| 3 | Confidence ≥ 0.75 with 3+ evidence → rule promoted to **ACTIVE** | State change span: candidate→active |
| 4 | Rule retrieved → guidance injected → agent generates **safe SQL** | New spans appear: retrieval + injection |
| 4+ | Post-promotion safe requests increase confidence further | Classification flips: unsafe→safe |

---

## Quick Start (One Command)

### Prerequisites
- Docker & Docker Compose
- Python 3.10+

### Start Everything

```bash
# Clone and enter the repository
git clone <repo>
cd evomind-observability

# Start SigNoz + EvoMind
docker compose up -d

# Wait 30 seconds for SigNoz to initialize
# Open SigNoz: http://localhost:3301
# EvoMind API: http://localhost:8000

# Run the demo
python demo.py
```

### Or Run EvoMind Standalone

```bash
# Install dependencies
pip install .

# Start with telemetry off (no SigNoz needed)
EVOMIND_OTEL_ENABLED=false python -m evomind

# Or point to your SigNoz instance
# Requires SigNoz at http://localhost:4317
python -m evomind
```

---

## Demo (5 Minutes)

Run `python demo.py` for an automated walkthrough:

1. **3 unsafe requests** → evidence accumulates, confidence reaches 0.80
2. **Rule promotes** → state change from candidate to active
3. **Guidance injected** → agent generates safe SQL with `?` placeholders
4. **Confidence grows** → 0.80 → 0.83 → continues on safe post-promotion requests

Each step prints colored output. Use `--auto` to skip pauses.

```bash
python demo.py          # interactive
python demo.py --auto   # run straight through
```

---

## SigNoz Dashboard

Open `http://localhost:3301` and navigate to the EvoMind dashboard:

| Panel | What It Shows |
|-------|--------------|
| Confidence Over Time | Line chart: 0.50 → 0.80 → 0.83+ |
| SQL Safety Ratio | Pie chart: safe vs unsafe vs ambiguous |
| Evidence Timeline | Bar chart: supporting vs contradicting |
| Recent Traces | Table: every request with key attributes |
| State Transitions | Table: every rule status change |
| Active Rules | Current ACTIVE rules count |

---

## Observability Story

EvoMind's key insight: **every decision point in the learning loop is a trace span**. This means:

- **Why did confidence increase?** → Open the trace → inspect the `confidence.updated` span
- **Which evidence caused it?** → Follow the `evidence.appended` span → check evidence type
- **Which request caused promotion?** → Find the trace with a `rule.state_change` span
- **Which SQL triggered the observation?** → Check `sql.generation` span attributes
- **Which trace recorded it?** → Every trace has `trace_id` linked to `request_id`

See [OBSERVABILITY_GUIDE.md](./OBSERVABILITY_GUIDE.md) for detailed instructions.

---

## Repository Structure

```
evomind-observability/
├── evomind/                    # Python package
│   ├── agent/                  # Deterministic SQL agent
│   ├── api/                    # FastAPI routes
│   ├── config/                 # Settings & environment
│   ├── evaluator/              # SQL safety classifier
│   ├── exceptions/             # Error types
│   ├── interfaces/             # Abstract base classes
│   ├── learning/               # EvidenceStore, ConfidenceEngine,
│   │                           # RuleRetriever, GuidanceInjector
│   ├── models/                 # BehavioralRule, Observation, etc.
│   ├── observation/            # ObservationFactory
│   ├── orchestration/          # Orchestrator, LifecycleManager
│   ├── persistence/            # SQLite repositories + schema
│   └── telemetry/              # OpenTelemetry tracer, meter,
│                               # MetricsRegistry, exporters
├── tests/                      # 214 tests, 92.73% coverage
├── ops/                        # OTEL collector config
├── screenshots/                # Demo screenshots
├── docs/                       # Architecture documentation
├── docker-compose.yml          # SigNoz + EvoMind
├── Dockerfile                  # EvoMind container
├── demo.py                     # Automated demo script
├── pyproject.toml
└── README.md
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.10, FastAPI |
| SQL Agent | Deterministic (pattern-based) |
| Learning Model | Beta-Bernoulli (α₀=1, β₀=1) |
| State Machine | Candidate → Active → Suspended → Archived |
| Tracing | OpenTelemetry (traces + metrics) |
| Observability Backend | SigNoz (ClickHouse + query service) |
| Data Export | OTLP gRPC |
| Persistence | SQLite (WAL mode) |
| Testing | pytest, pytest-cov (214 tests, 92.73%) |

---

## Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `evomind.requests.total` | Counter | Total requests processed |
| `evomind.sql.safety.ratio` | ObservableGauge | Ratio of safe SQL |
| `evomind.rule.confidence` | ObservableGauge | Current rule confidence |
| `evomind.rule.evidence.count` | ObservableGauge | Total evidence for rule |

---

## Judge Quick-Start

See [JUDGE_GUIDE.md](./JUDGE_GUIDE.md) for a 2-minute evaluation checklist.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [DEMO.md](./DEMO.md) | Step-by-step demo script |
| [OBSERVABILITY_GUIDE.md](./OBSERVABILITY_GUIDE.md) | How to investigate with SigNoz |
| [TRACE_WALKTHROUGH.md](./TRACE_WALKTHROUGH.md) | Detailed trace anatomy |
| [JUDGE_GUIDE.md](./JUDGE_GUIDE.md) | Hackathon judging checklist |
| [HACKATHON_SUBMISSION_AUDIT.md](./HACKATHON_SUBMISSION_AUDIT.md) | Final pre-submission verification |

---
