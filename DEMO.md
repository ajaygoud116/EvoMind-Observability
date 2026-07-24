# EvoMind Observability — Demo Script

**Duration:** ~5 minutes  
**Objective:** Show that a judge can investigate an AI agent's behavioral change using SigNoz alone.

---

## Setup

```bash
# Terminal 1: Start EvoMind + SigNoz
docker compose up -d
# Wait ~30 seconds for SigNoz to initialize

# Terminal 2: Run the demo
python demo.py --auto
```

Or run standalone (no SigNoz needed for the demo script):

```bash
EVOMIND_OTEL_ENABLED=false python -m evomind &
python demo.py --auto
```

---

## Demo Walkthrough

### Step 1: Initial State (30 seconds)

**Action:** Open SigNoz at `http://localhost:8080`.

**What to show:**
- Empty Traces view (no requests yet)
- Metrics dashboard with no data points
- Explain: "The system is fresh. The behavioral rule exists as a Candidate with confidence 0.50, but no evidence has been collected."

**Key point:** Before any learning, there is nothing to observe.

---

### Step 2: Three Unsafe Requests (1 minute)

**Action:** Run `python demo.py --auto` (or submit requests manually).

**What happens:**
- 3 requests with inline-value SQL (e.g., `SELECT * FROM users WHERE id = 5`)
- Each classified as **unsafe** → creates **supporting** evidence (pre-promotion semantics)
- Confidence climbs: 0.50 → 0.67 → 0.75 → 0.80

**SigNoz view:**
- 3 traces appear
- Each trace shows: no rule retrieved, no guidance, unsafe SQL, supporting evidence
- Confidence gauge: rising from 0.50

**Narration:**
> "Three requests. The agent generates SQL with inline values — unsafe. Each unsafe classification creates supporting evidence. Watch confidence climb from 0.50 to 0.80."

---

### Step 3: Rule Promotion (30 seconds)

**What happens:** After the 3rd request, confidence 0.80 ≥ 0.75 with 3+ evidence → **rule promotes to ACTIVE**.

**SigNoz view:**
- The 3rd trace includes a new span: `evomind.rule.state_change`
- Span attributes: `from_status=candidate`, `to_status=active`
- Rule state in metrics: now ACTIVE

**Narration:**
> "The third request triggered a state change. The rule is now ACTIVE. It will be retrieved on the next request."

**How to find it in SigNoz:**
1. Open the 3rd trace
2. Find the `evomind.rule.state_change` span
3. Read the `reason` attribute

---

### Step 4: First Guided Request (1 minute)

**Action:** The 4th request "Delete user with id 1" is submitted.

**What happens:**
- Rule is **retrieved** (now ACTIVE)
- Guidance is **injected**: "Always use parameterized queries"
- Agent generates: `DELETE FROM users WHERE id = ?`
- Classified as **safe** → creates **supporting** evidence (post-promotion semantics)
- Confidence: 0.80 → 0.83

**SigNoz view:**
- 4th trace shows 2 new spans:
  - `evomind.rule.retrieval`: found=true, rule_id, confidence=0.80
  - `evomind.guidance.injection`: injected=true
- SQL generation shows `?` placeholders instead of inline values
- Classification is now **safe**

**Narration:**
> "This is the key moment. The rule is active, so it gets retrieved. Guidance is injected. The agent generates **parameterized SQL**. The behavior has changed — and every step is visible in the trace."

**Compare with trace #1:**
- Use SigNoz trace comparison
- Show: trace #1 has no retrieval/injection spans, trace #4 has both
- Show: trace #1 classification=unsafe, trace #4 classification=safe

---

### Step 5: Continued Growth (30 seconds)

**Action:** 2 more safe requests.

**What happens:**
- Both generate safe SQL
- Confidence: 0.83 — held steady (ambiguous classification produces neutral evidence)

**SigNoz view:**
- All recent traces show safe SQL with ? placeholders
- Confidence gauge reflects evidence type: safe → supporting → +confidence; ambiguous → neutral → no change

**Narration:**
> "Safe SQL with ? placeholders reinforces the behavior. Confidence grows on each supporting observation."

---

### Step 6: Investigation (1 minute)

**Action:** Answer these questions live using SigNoz:

| Question | How to Answer |
|----------|---------------|
| Why did behavior change? | Confidence-over-time chart shows inflection at trace #3 |
| Which evidence caused it? | Evidence table filtered by rule_id |
| Why was the rule trusted? | Confidence (0.80) > threshold (0.75) with 3+ evidence |
| Did behavior improve? | Compare trace #1 (unsafe) with trace #6 (safe) |

**Narration:**
> "Every question the judge asks can be answered through SigNoz. No source code needed."

---

## Demo Script Commands

### Manual requests (alternative to demo.py):

```bash
# 1. Health check
curl http://localhost:8000/api/health

# 2. Three unsafe requests
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me users where id equals 5"}'

curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Insert a new order for user 10 with amount 99.99"}'

curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Delete user with id 1"}'

# 4. First guided request
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Delete user with id 1"}'

# 5-6. Continued safe requests
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me orders for customer 42"}'

curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Insert user named Alice with email alice@test.com"}'
```

---

## Demo Success Checklist

- [ ] SigNoz is running at http://localhost:8080
- [ ] EvoMind is running at http://localhost:8000
- [ ] `python demo.py` produces clear colored output
- [ ] Step 1: Empty state visible in SigNoz
- [ ] Step 2: 3 unsafe requests → confidence 0.80
- [ ] Step 3: Promotion visible in `evomind.rule.state_change` span
- [ ] Step 4: Rule retrieved + guidance injected → safe SQL
- [ ] Step 5: Confidence 0.83+ after 6 requests
- [ ] Step 6: All investigation questions answerable via SigNoz
- [ ] Traces visible in SigNoz with all attributes
- [ ] Metrics visible in SigNoz dashboard
