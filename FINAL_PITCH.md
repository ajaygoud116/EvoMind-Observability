# EvoMind Observability — Final Pitch

---

## One Sentence

EvoMind makes an AI agent's behavioral learning lifecycle — every evidence signal, confidence update, and rule transition — observable as OpenTelemetry traces and metrics in SigNoz.

---

## 30-Second Pitch

"AI agents change behavior over time. When they do, you need to know why.

EvoMind demonstrates that every step of behavioral learning — observing unsafe SQL, accumulating evidence, updating confidence, promoting a rule, injecting guidance — can be instrumented as OpenTelemetry spans. Every decision has a trace. Every confidence change has a mathematically verified delta. Every state transition has a recorded reason.

Open SigNoz, find the trace, and you know exactly why the agent changed its behavior — without reading source code."

---

## 2-Minute Pitch

**The problem:** AI agents generate SQL. Sometimes it's safe (parameterized). Sometimes it's unsafe (string interpolation — SQL injection risk). The agent learns over time: unsafe examples accumulate, a behavioral rule promotes, guidance gets injected, and the agent generates safer SQL.

But when a judge asks "why did the agent change its behavior?", the answer today requires reading source code or trusting the developer's word.

**What we built:** EvoMind is a demonstration that every step of this behavioral learning process can be made fully observable.

Here's how it works:

1. An agent receives a prompt like "Show me users where id equals 5" and generates `SELECT * FROM users WHERE username = 'admin'`.
2. The SQL safety evaluator classifies it as unsafe — inline string values are a SQL injection risk.
3. Each unsafe classification becomes supporting evidence for a behavioral rule called "use parameterized queries."
4. A Beta-Bernoulli confidence engine tracks the rule's confidence using the formula `confidence = α/(α+β)` where α counts supporting evidence and β counts contradicting.
5. After 3 unsafe requests, confidence reaches 0.80, crossing the 0.75 promotion threshold. The rule promotes from CANDIDATE to ACTIVE.
6. On the next request, the rule is retrieved, guidance is injected ("always use ? placeholders"), and the agent generates `DELETE FROM users WHERE id = ?` — safe, parameterized SQL.

Every single step emits an OpenTelemetry span with structured attributes. All of it lands in SigNoz where a judge can investigate without touching source code.

**Why this matters:** As AI agents move from demo to production, understanding why they change behavior becomes critical. EvoMind shows that behavioral learning doesn't have to be a black box. It can be observable, auditable, and explainable — using the same OpenTelemetry infrastructure already adopted by the industry.

---

## 5-Minute Technical Walkthrough

### Architecture (30 seconds)

```
User Prompt → RuleRetriever → GuidanceInjector → SQLAgent → SafetyEvaluator
→ ObservationFactory → EvidenceStore → ConfidenceEngine → API Response
                                          │
                                    OpenTelemetry SDK
                                          │
                                      SigNoz
```

8 components. 1 orchestrator. Each step is an OTel span. No component calls another directly — the orchestrator coordinates everything.

### The Learning Model (1 minute)

Beta-Bernoulli conjugate model:

- **Prior:** `Beta(α₀=1, β₀=1)` — uniform distribution, no prior belief.
- **Supporting evidence:** `α += 1` (rule is needed or worked).
- **Contradicting evidence:** `β += 1` (rule failed).
- **Confidence:** `E[Beta(α,β)] = α/(α+β)`.
- **Variance:** `Var[Beta(α,β)] = αβ/((α+β)²(α+β+1))` — decreases as evidence accumulates.

Mathematical results of running the demo:
```
Start:   α=1, β=1,  confidence=0.500
Req 1:   α=2, β=1,  confidence=0.667, delta=+0.167
Req 2:   α=3, β=1,  confidence=0.750, delta=+0.083
Req 3:   α=4, β=1,  confidence=0.800, delta=+0.050  → PROMOTION
Req 4:   α=5, β=1,  confidence=0.833, delta=+0.033
Req 5:   α=5, β=1,  confidence=0.833, delta=0.000   (NEUTRAL evidence)
```

### The Evidence Semantics (1 minute)

Pre-promotion vs post-promotion evidence mapping prevents a semantic error:

| Context | UNSAFE | SAFE | AMBIGUOUS |
|---------|--------|------|-----------|
| Pre-promotion | SUPPORTING (rule needed) | BASELINE (no signal) | NEUTRAL (no signal) |
| Post-promotion | CONTRADICTING (rule failed) | SUPPORTING (rule worked) | NEUTRAL (no signal) |

Before a rule is active, safe SQL doesn't prove the rule is unnecessary — it just means the agent happened to be safe. After the rule is active, safe SQL proves the rule worked.

### The Observability Layer (1 minute)

7 span types, each with structured attributes:

| Span | Key Attributes | What It Answers |
|------|---------------|-----------------|
| `evomind.rule.retrieval` | `rule.retrieved`, `rule.id`, `rule.confidence` | Was a rule found? |
| `evomind.guidance.injection` | `guidance.injected`, `guidance.length` | Was guidance applied? |
| `evomind.sql.generation` | `app.sql.generated`, `app.sql.length` | What SQL was produced? |
| `evomind.sql.evaluation` | `classification`, `detected.patterns` | Was it safe? |
| `evomind.evidence.appended` | `evidence.id`, `evidence.delta` | What evidence was created? |
| `evomind.confidence.updated` | `confidence.before`, `confidence.after`, `confidence.delta` | How did confidence change? |
| `evomind.rule.state_change` | `from_status`, `to_status`, `reason` | Did the rule promote? |

4 metric instruments (1 counter, 3 observable gauges) complement the traces.

### Verification (30 seconds)

- 214 tests pass, 93% coverage
- Every evidence delta is mathematically verified: `delta == after - before`
- The demo is deterministic: same prompts → same output
- All P0 bugs confirmed fixed via runtime tests

---

## 10-Minute Demo Script

### Setup (1 minute)

```
Terminal 1: docker compose up -d                      # Start SigNoz + EvoMind
Terminal 2: curl http://localhost:8000/api/health      # Verify API is up
```

Show: `{"status": "ok", "version": "0.1.0", "service": "evomind-observability"}`

"Before any requests. No traces, no metrics. The rule exists as a CANDIDATE with confidence 0.50, but no evidence has been collected."

### Step 1: Three Unsafe Requests (2 minutes)

```
python demo.py --auto
```

Show the output progressing through 6 requests. Point to each:

- Request 1: `SELECT * FROM users WHERE username = 'admin'` → **unsafe** → confidence 0.67
- Request 2: `INSERT INTO users (name, email) VALUES ('admin', '...')` → **unsafe** → confidence 0.75
- Request 3: `DELETE FROM users` → **unsafe** → **0.80 → status_changed=True → to_status=active**

"Three unsafe requests. Each one increases confidence by a mathematically predictable amount. The system never guesses — it counts."

### Step 2: Trace Investigation (2 minutes)

Switch to SigNoz. Open Traces view. Filter by `evomind-observability`.

Open trace #1:
- Point to `evidence.appended` span: `delta=0.1667`
- Point to `confidence.updated` span: `before=0.50, after=0.67`
- "You can verify: 0.67 - 0.50 = 0.17. The math checks out."

Open trace #3:
- Point to `state_change` span: `from_status=candidate, to_status=active`
- Point to `reason` attribute: describes the promotion criteria
- "The rule promoted because confidence 0.80 >= threshold 0.75 with 3 supporting evidence. All visible in the trace."

### Step 3: Behavior Change (2 minutes)

Open trace #4:
- Point to `rule.retrieval` span: `retrieved=true`
- Point to `guidance.injection` span: `injected=true`
- Point to `sql.generation` span: `DELETE FROM users WHERE id = ?`
- Point to `evaluation` span: `classification=safe`

Open trace #1 side-by-side:
- No retrieval span (no active rule)
- No injection span (no guidance)
- `classification=unsafe`
- `sql=DELETE FROM users` (no WHERE clause, no parameterization)

"The difference between trace #1 and trace #4 is the entire demo. Before: unsafe SQL, no rule, no guidance. After: safe SQL, rule retrieved, guidance injected. Every difference is visible in the spans."

### Step 4: Metrics Dashboard (1 minute)

Switch to Dashboard view. Show:
- **Confidence Over Time:** Rising line from 0.50 to 0.83
- **SQL Safety Ratio:** Shifts from all-unsafe to safe
- **Evidence Timeline:** Supporting evidence per request

"Metrics tell the trend. Traces tell the story. You need both for complete observability."

### Step 5: Database Verification (1 minute)

```bash
sqlite3 evomind.db "SELECT confidence_before, confidence_after, delta FROM evidence_records;"
```

Show the results match the API response values.

"The database confirms what the traces show. Every number is consistent across API, traces, metrics, and storage."

### Step 6: Q&A (1 minute)

"What about LangSmith?" — LangSmith traces LLM calls. We trace the learning system around the LLM call. They answer different questions. LangSmith: "What did the LLM output?" EvoMind: "Why did the agent's behavior change over time?"

"Is this production-ready?" — No. It's a demonstration. Mock agent, SQLite, in-memory metrics. But the architecture is designed for production — interfaces, DI, OTel-native instrumentation, verifiable math.

"What's actually innovative?" — Representing behavioral learning lifecycle steps as OTel spans with mathematically verified deltas. Prior work (LangSmith, Arize) traces model outputs. Nobody traces the learning loop itself.
