# EvoMind Observability — Judge Guide

**Estimated evaluation time:** 5 minutes

This guide helps hackathon judges evaluate EvoMind Observability by answering the key questions the project is designed to address.

---

## 1. Does the system work? (30 seconds)

### Run the health check

```bash
curl http://localhost:8000/api/health
```

Expected: `{"status": "ok", "version": "0.1.0", "service": "evomind-observability"}`

### Run the demo

```bash
python demo.py --auto
```

Expected: Colored output showing 6 requests, culminating in safe SQL and confidence 0.83+.

**Pass criteria:** The API is running, requests are processed, SQL is generated.

---

## 2. Does the system learn? (1 minute)

Look at the demo output:

| Request | SQL Safety | Confidence | Status |
|---------|-----------|-----------|--------|
| 1 | unsafe | 0.67 | candidate |
| 2 | unsafe | 0.75 | candidate |
| 3 | unsafe | **0.80** | **active** |
| 4 | **safe** | 0.83 | active |
| 5 | ambiguous | 0.83 | active |
| 6 | ambiguous | 0.83 | active |

**Key observations:**
- Confidence rises from 0.50 to 0.83
- Post-promotion: guided requests produce safe SQL; non-guided requests may produce ambiguous (e.g., SELECT *)
- SQL safety flips from unsafe to safe at request 4 (after promotion)
- The system demonstrably learns from experience

**Pass criteria:** Confidence increases over time. SQL behavior improves.

---

## 3. Is the learning observable? (1 minute)

Open SigNoz at `http://localhost:8080`.

### Verify traces exist

1. Go to **Traces** → filter by `evomind-observability`
2. You should see 6 traces (one per request)

### Verify metrics exist

1. Go to **Dashboard** → the EvoMind dashboard
2. Check the Confidence Over Time panel — should show a rising line

### Find a state change

1. Search for traces containing `evomind.rule.state_change`
2. Open the trace — the `reason` attribute explains why promotion occurred

**Pass criteria:** Traces, metrics, and state changes are visible in SigNoz.

---

## 4. Can you investigate root cause? (1 minute)

Answer these questions using **only SigNoz** (no source code):

| Question | How to Find the Answer | Attribute to Check |
|----------|----------------------|-------------------|
| Why did confidence increase? | Open a trace → `confidence.updated` span | `confidence.delta` |
| Which evidence caused it? | Preceding `observation.created` span | `evidence_type` |
| What SQL was generated? | `sql.generation` span | `app.sql.generated` |
| Was guidance injected? | Look for `guidance.injection` span | `guidance.injected` |
| When did the rule promote? | Find `state_change` span | `from_status`, `to_status` |
| Is the rule active now? | Latest `lifecycle.complete` span | `to_status` |

**Pass criteria:** All 6 questions are answerable through SigNoz alone.

---

## 5. Does the architecture hold up? (1 minute)

### Review these architectural decisions:

| Decision | Implementation | Why It Matters |
|----------|---------------|----------------|
| Beta-Bernoulli model | α₀=1, β₀=1, confidence = α/(α+β) | Simple, mathematically sound, conjugate prior |
| Three-state semantics | Pre/post promotion changes evidence mapping | Prevents misleading evidence before rule is trusted |
| State machine | Candidate → Active → Suspended → Archived | Rules have a clear lifecycle |
| OpenTelemetry-native | Every decision is a span | Complete audit trail without extra instrumentation |
| Deterministic agent | Pattern-based SQL generation | Reproducible demo — no LLM flakiness |
| MetricsRegistry | 4 instruments: Counter + 3 ObservableGauges | Metrics complement traces |

### Verify the test suite:

```bash
pytest tests/ --cov=evomind --cov-fail-under=90
```

Expected: **214 passed, 92.73% coverage**

**Pass criteria:** Architecture is coherent, test suite is comprehensive.

---

## 6. Is the demo reproducible? (30 seconds)

```bash
# Clean start
rm -f evomind.db
python demo.py --auto          # all 6 requests succeed

# Reset and re-run
rm -f evomind.db
python demo.py --auto          # identical output
```

**Pass criteria:** Running the demo twice with a clean database produces the same results.

---

## 7. Final Scoring Checklist

| Criterion | Weight | Evidence |
|-----------|--------|----------|
| System works | Required | `curl /api/health` returns 200 |
| System learns | Required | Confidence rises, SQL improves |
| Learning is observable | High | Traces + metrics in SigNoz |
| Root cause investigation | High | All 6 questions answerable |
| Architecture is sound | Medium | Clean separation, frozen backend |
| Demo is reproducible | Medium | Identical output on re-run |
| Documentation is clear | Medium | README, DEMO.md, JUDGE_GUIDE.md |
| Testing is comprehensive | Low | 214 tests, 92.73% coverage |

---

## Quick Reference

| URL | Purpose |
|-----|---------|
| `http://localhost:8080` | SigNoz dashboard |
| `http://localhost:8000` | EvoMind API |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/api/health` | Health check |

```bash
# API quick reference
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me users"}'

# Test suite
pytest tests/ --cov=evomind --cov-fail-under=90

# Demo
python demo.py --auto
```
