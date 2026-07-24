# EvoMind Observability — Demo Plan

## Demo Objective

Demonstrate that a judge can investigate an AI agent's behavioral change using **SigNoz alone** — without reading source code — and answer every question from the success criteria.

---

## Setup

| Item | Details |
|---|---|
| SigNoz | Self-hosted via Docker on localhost:8080 |
| EvoMind service | Running on localhost:8000 |
| Client | `curl`, a bash script, or the SigNoz dashboard |
| Pre-seeded rule | `use_parameterized_sql` with default params |
| Agent | Mock mode (deterministic) |

**Pre-flight check:**
1. SigNoz dashboard loads at `http://localhost:8080`
2. EvoMind health endpoint: `GET /api/health` returns `{"status": "ok"}`
3. Request `curl -X POST http://localhost:8000/api/query -H "Content-Type: application/json" -d '{"prompt": "test"}'` returns 200 with SQL

---

## Demo Walkthrough (6 Steps)

### Step 1: Initial State — "No Learning Has Occurred"

**Action:** Open SigNoz dashboard → Traces view → Show empty state (no traces yet).

**Narration:**
> "This is EvoMind Observability. The system is fresh. No requests have been processed. No evidence exists. The behavioral rule exists as a Candidate but has zero observations."

**SigNoz State:**
- Traces: empty
- Metrics: no data
- Behavioral rule: `status=candidate, confidence=0.50, alpha=1, beta=1, evidence_count=0`

**Questions the judge can answer:**
- Was there ever a behavioral rule? Yes, it exists but is not active.
- Was it retrieved? No — no requests have been made.

---

### Step 2: Three Unsafe Requests — "Evidence Accumulation"

**Action:** Submit 3 requests with prompts that should generate parameterized SQL:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me users where id equals 5"}'
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Insert a new order for user 10 with amount 99.99"}'
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Update product price to 29.99 where id is 3"}'
```

**Narration:**
> "Three requests. The agent generates SQL using string interpolation every time — unsafe. Each one is classified as unsafe, creating supporting evidence. Watch confidence climb from 0.50 to 0.80."

**SigNoz State:**
- Traces: 3 traces, each showing:
  - `rule.retrieval`: found=false, reason="no_active_rules"
  - `guidance.injection`: not created
  - `sql.generation`: SQL with literal values
  - `sql.evaluation`: classification=unsafe
  - `observation.created`: evidence_type=supporting
  - `confidence.updated`: 0.50→0.67→0.75→0.80
- Metrics: `evomind.rule.confidence` gauge = 0.80

**Questions the judge can answer:**
- Was a behavioral rule available? Yes, but it was Candidate, not Active.
- Was it retrieved? No, it was not active.
- What SQL was generated? Unsafe — literal values in WHERE clauses.
- Was it safe? No, each classified as unsafe.
- Did confidence change? Yes, from 0.50 to 0.80.

---

### Step 3: Rule Promotion — "The Learning Event"

**Action:** This happens automatically after Step 2. No manual action.

**Narration:**
> "The third request pushed confidence to 0.80 — above the 0.75 promotion threshold, with 3 observations meeting the minimum evidence requirement. The behavioral rule has been promoted to Active."

**SigNoz State:**
- The third trace shows an additional span: `evomind.rule.state_change`
- Span attributes: `from_status=candidate`, `to_status=active`, `reason=confidence_threshold_met`
- Rule now: `status=active, confidence=0.80`

**How to find it in SigNoz:**
1. Open the third trace
2. Look for the `evomind.rule.state_change` span
3. See the `rule.status.from` and `rule.status.to` attributes

**Questions the judge can answer:**
- Did a behavioral rule change state? Yes, Candidate → Active.
- Why? Confidence crossed the promotion threshold.
- Which evidence caused it? Three supporting evidence records from unsafe SQL classifications.

---

### Step 4: First Guided Request — "The Behavior Change"

**Action:** Submit a 4th request:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Delete user with id 7"}'
```

**Narration:**
> "This time is different. The rule is Active, so it gets retrieved. Guidance is injected: 'Always use parameterized queries'. The agent now generates safe SQL with ? placeholders."

**SigNoz State (4th trace):**
- `rule.retrieval`: found=true, rule_id, confidence=0.80
- `guidance.injection`: injected=true, text="IMPORTANT: Always use parameterized..."
- `sql.generation`: `DELETE FROM users WHERE id = ?`
- `sql.evaluation`: classification=safe
- `observation.created`: evidence_type=supporting (safe + guidance = supporting)
- `confidence.updated`: 0.80→0.83

**How to find it in SigNoz:**
1. Open the 4th trace
2. Compare with the 1st trace side-by-side (SigNoz trace comparison feature)
3. Note the new spans (guidance.injection) and changed classification

**Questions the judge can answer:**
- Was a rule retrieved? Yes — for the first time.
- Which rule? `use_parameterized_sql`.
- What confidence did it have? 0.80.
- Was guidance injected? Yes.
- What SQL was generated? Parameterized — safe.
- Did behavior improve? Yes, from unsafe to safe.

---

### Step 5: Continued Improvement — "Confidence Growth"

**Action:** Submit 2 more requests:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me orders for customer 42"}'
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Insert user named Alice with email alice@test.com"}'
```

**Narration:**
> "Two more requests, both safe. Confidence continues: 0.83 on the first safe request, held steady on the next (ambiguous → neutral)."

**SigNoz State:**
- Metric `evomind.rule.confidence` now shows: 0.50 → 0.67 → 0.75 → 0.80 → 0.83 → 0.83
- All recent traces show safe SQL with `?` placeholders

**Questions the judge can answer:**
- Did behavior improve and stabilize? Yes — 3 consecutive safe responses.

---

### Step 6: Investigation — "The Root Cause Analysis"

**Action:** Use SigNoz to answer specific investigation questions live.

**Narration:**
> "Now let's investigate. A new engineer joins the team. They see behavior changed from unsafe to safe SQL. They want to know why."

**Investigation Script:**

**Q1: "Why did the behavior change?"**

1. Open the Overview dashboard
2. Look at the confidence-over-time chart: see confidence rising from 0.50 to 0.83
3. Notice the inflection point at trace #3 where the rule was promoted
4. Click on trace #4 to see the first guided request

**Q2: "Which evidence caused it?"**

1. Open the Evidence table
2. Filter by rule = `use_parameterized_sql`
3. View 6 evidence records: 3 supporting (unsafe SQL), 3 supporting (safe SQL after guidance)
4. See the exact confidence before/after for each

**Q3: "Why was the rule trusted?"**

1. Check the confidence threshold configuration (visible in rule metadata span)
2. See that confidence (0.80) exceeded promotion_threshold (0.75) with min_evidence (3) met
3. The math is visible and auditable

**Q4: "What contradictory evidence exists?"**

1. Filter evidence by type = contradicting
2. (In this demo) none exists — the rule has been consistently supported

**Q5: "Did behavior improve?"**

1. Compare trace #1 (unsafe SQL in sql.generation span) with trace #6 (safe SQL)
2. Classification changed from unsafe to safe
3. Confidence increased from 0.50 to 0.83

---

## Demo Variation: Regression Scenario

To demonstrate regression (behavior getting worse), add an optional Step 7:

### Step 7: Regression — "The Relapse"

**Action:** Temporarily disable the mock agent's guidance response (simulate an LLM failure). Submit 2 more requests.

```bash
# Agent now ignores guidance and returns unsafe SQL
curl -X POST ...  # returns unsafe SQL despite guidance
curl -X POST ...  # returns unsafe SQL despite guidance
```

**SigNoz State:**
- `sql.evaluation`: classification=unsafe
- `observation.created`: evidence_type=contradicting (unsafe + guidance = contradicting)
- `confidence.updated`: 0.83 → 0.75 → 0.67

**Questions the judge can answer:**
- Did behavior regress? Yes — back to unsafe SQL.
- Why? Confidence dropped due to contradicting evidence.
- Which observations contradict? The two unsafe SQLs generated despite guidance.

---

## Dashboard Panels to Show

During the demo, the judge should see these SigNoz panels:

1. **Confidence Over Time** (line chart)
   - X-axis: request sequence
   - Y-axis: confidence (0.0–1.0)
   - Annotation at promotion point

2. **Classification Distribution** (pie chart)
   - safe vs unsafe vs ambiguous
   - Before promotion vs after promotion (split)

3. **Recent Traces** (table)
   - trace_id, request_id, classification, rule_retrieved, confidence, timestamp

4. **Evidence Timeline** (bar chart)
   - supporting (green) vs contradicting (red) per request
   - Cumulative view

5. **State Transition Log** (table)
   - rule_id, from_status, to_status, reason, timestamp

---

## Demo Success Checklist

- [ ] SigNoz is running and accessible
- [ ] EvoMind service is running
- [ ] Rule is seeded (one time)
- [ ] Step 1: Empty state visible
- [ ] Step 2: 3 unsafe requests → confidence 0.80
- [ ] Step 3: Promotion evident in trace
- [ ] Step 4: First guided request shows behavior change
- [ ] Step 5: Confidence continues to grow
- [ ] Step 6: Investigation questions all answerable via SigNoz
- [ ] (Optional) Step 7: Regression scenario demonstrates contradicting evidence
