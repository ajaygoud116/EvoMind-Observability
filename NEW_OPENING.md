# EvoMind — First 120 Seconds (Redesign)

**Constraint:** No backend changes. No architecture changes.  
**Goal:** Judge understands the problem, why current tools fail, what EvoMind demonstrates, and why to keep watching — within 2 minutes.

---

## The Problem with the Current Opening

**Current:** Lead with three unsafe requests. The first 90 seconds show "unsafe, unsafe, unsafe" — negative framing. The judge sees scrolling terminal text before understanding why they should care.

**Problem:** The wow moment (behavior change) doesn't arrive until request 4 at ~3:00. The judge decides at :30.

**Fix:** Invert the order. Show the result first. Create a mystery. Then solve it.

---

## New Opening Script (120 seconds, timed)

### :00–:10 — The Hook (One Image)

The presenter has two terminal windows side by side on screen. Both show a single command and its output.

**Left terminal:**
```
$ BEFORE: curl -X POST ... -d '{"prompt": "Delete user with id 1"}'
{ "sql": "DELETE FROM users", "classification": "unsafe" }
```

**Right terminal:**
```
$ AFTER:  curl -X POST ... -d '{"prompt": "Delete user with id 1"}'
{ "sql": "DELETE FROM users WHERE id = ?", "classification": "safe" }
```

**Presenter says:**

> "Same prompt. Same agent. Different SQL. Something changed the agent's behavior between these two requests. No code was deployed. No configuration was changed. The agent learned."

### :10–:30 — The Question (The Gap)

**Presenter says:**

> "If you're deploying AI agents, this question keeps you up at night: why did the behavior change? Was it intentional? Was it a bug? Would it regress?"

**Action:** Presenter holds up a phone.

> "LangSmith answers: what SQL did the agent generate for this prompt? LangFuse answers: which prompt version was used? Arize answers: is the model drifting?"

**Action:** Puts the phone down.

> "None of them answer this question: WHY did the behavior change across requests?"

### :30–:50 — The Answer (First Wow)

**Action:** Presenter hits Enter. The terminal shows a single command — no Docker, no SigNoz login:

```
$ python -c "
import requests, json
r1 = requests.post('http://localhost:8000/api/query',
      json={'prompt': 'Delete user with id 1'}).json()
r4 = requests.post('http://localhost:8000/api/query',
      json={'prompt': 'Delete user with id 1'}).json()
print('Before:', 'DELETE FROM users' in r1['sql'], '| unsafe:', r1['classification'])
print('After: ', '?' in r4['sql'],           '| safe:',   r4['classification'])
print('Delta: ', r1['confidence'], '->', r4['confidence'])
print('Why:   ', 'Rule promoted' if r4['rule_retrieved'] else 'No rule')
"
```

**Output:**
```
Before: True | unsafe: unsafe
After:  True | safe: safe
Delta:  0.5 -> 0.8
Why:    Rule promoted, guidance injected, SQL parameterized
```

**Presenter says:**

> "Three API calls. I can see: the behavior changed because a rule promoted to active, guidance was injected, and the agent started generating parameterized SQL. All visible in the API response. No source code. No dashboard login."

### :50–1:10 — The Trace (Second Wow)

**Action:** Open a pre-opened browser tab showing SigNoz trace #4 (the enforcement trace). Or, even faster: show a screenshot in the slide deck.

**Presenter says:**

> "Every single decision that caused this change is recorded as an OpenTelemetry span. Let me open trace #4 — the request where the behavior changed."

Point to three spans in the flamegraph:

| Span | Key Attribute | Shows |
|------|--------------|-------|
| `evomind.rule.retrieval` | `retrieved: true` | Rule exists and was found |
| `evomind.guidance.injection` | `injected: true` | Guidance was applied |
| `evomind.sql.generation` | `sql: DELETE ... WHERE id = ?` | Output changed |

> "These spans didn't exist in trace #1. The difference between trace #1 and trace #4 is the entire story of how the agent learned."

### 1:10–1:30 — The Mechanism (The "How")

**Presenter says:**

> "How did the rule get there? Three unsafe requests created three pieces of supporting evidence. Each one updated a Beta-Bernoulli confidence score."

Show on screen:
```
Evidence 1: confidence 0.50 → 0.67  (delta +0.17)
Evidence 2: confidence 0.67 → 0.75  (delta +0.08)
Evidence 3: confidence 0.75 → 0.80  (delta +0.05)  → PROMOTED
```

> "At 0.80 with 3+ evidence, the rule promoted. Every delta is verified: 0.67 − 0.50 = 0.17. 0.75 − 0.67 = 0.08. The math is transparent, the evidence is recorded, the state change is traced."

### 1:30–2:00 — Why Keep Watching

**Presenter says:**

> "In the next 3 minutes I'll show you three things no other observability tool can do:

> 1. **Root cause without source code** — I'll answer five questions about this behavior change using only SigNoz.
> 2. **Database verification** — I'll query SQLite and prove every confidence delta in the traces matches the stored evidence.
> 3. **Reproducibility** — I'll reset the database and run the exact same demo, producing the exact same output.

> The system is deterministic. The observability is complete. Everything you see is verifiable.

> If you deploy AI agents, you need to know why they change behavior. EvoMind shows you how to see it."

---

## New Demo Order

| Time | What Judge Sees | What Judge Learns |
|------|----------------|-------------------|
| :00 | Before/after SQL comparison | Same prompt, different output |
| :10 | Question: "Why did it change?" | Existing tools can't answer |
| :30 | 3 API calls + response inspection | Answer is in the API response |
| :50 | SigNoz trace with spans | Every decision is a span |
| 1:10 | Confidence trajectory | Math is transparent |
| 1:30 | Preview of what's next | Full investigation coming |
| 2:00 | (Transition to deep demo) | — |

**Key changes from current demo order:**

| Current | New |
|---------|-----|
| Step 1: 3 unsafe requests (negative) | Step 1: Before/After contrast (mystery) |
| Step 2: Verify promotion | Step 2: Answer in API response |
| Step 3: Enforcement (the wow moment, late) | Step 3: SigNoz trace (wow, early) |
| Step 4-6: Safe requests, growth | Step 4: Mechanism explanation |
| — | Step 5: Preview of deep dive |

**The three unsafe requests move from Step 1 to Step 4** — after the judge already understands WHY they matter.

---

## New First Dashboard View

**What a judge should see first in SigNoz (or as a pre-captured screenshot):**

**Option A (SigNoz running):** Navigate directly to **Traces** → filter `evomind-observability` → select trace #4. Show the span list.

**Option B (Screenshot in deck):** A single slide showing:

```
TRACE #4 — "Delete user with id 1"

──────────────────────────────────────────────────
evomind.request                               OK
├── evomind.rule.retrieval   retrieved=true   ✓
├── evomind.guidance.injection injected=true  ✓
├── evomind.sql.generation   WHERE id = ?     ✓
├── evomind.sql.evaluation   classification=  safe
├── evomind.evidence.appended delta=+0.0333
├── evomind.confidence.updated 0.80 → 0.83
└── evomind.lifecycle.complete                  ✓
──────────────────────────────────────────────────

Compare with TRACE #1:
✗ No rule retrieval   ✗ No guidance   ✗ Unsafe SQL
```

**Key design principles:**
1. Show trace #4 FIRST (not trace #1) — it has MORE spans, more story to tell
2. Use ✓/✗ icons — instant visual scan
3. Compare with trace #1 as a sidebar — immediate contrast
4. Show only the span names and ONE key attribute per span — no attribute overload

---

## Expected Judge Reactions

### At :10 (Before/After comparison)

> "Wait, same prompt produced different SQL? How?"

Judge is now curious. The mystery is established.

### At :30 (Three API calls)

> "Oh, the answer is in the response fields. That's actually useful."

Judge sees practical value. The tool answers the question directly.

### At :50 (SigNoz trace)

> "Every step is a span? Let me see if that's really true..."

Judge is now inspecting. The novelty is visible.

### At 1:10 (Confidence trajectory)

> "This is just counting. I could verify this."

Judge trusts the mechanism. The model is simple enough to be credible.

### At 1:30 (Preview)

> "OK, show me the rest."

Judge is engaged. The 120-second bar is cleared.

---

## What NOT to Do in the First 2 Minutes

| Don't | Why |
|-------|-----|
| Start with "The Problem: SQL injection" | Too narrow. The problem is behavioral change, not SQL injection. |
| Show three unsafe requests first | 90 seconds of "unsafe, unsafe, unsafe" is negative and boring. |
| Explain Beta prior (1,1) | Too much math too early. Show the trajectory, not the formula. |
| Talk about OpenTelemetry protocols | A judge doesn't care about OTLP gRPC vs HTTP. Show the spans. |
| Ask judge to run Docker | 5 containers + 30 seconds = 30% of their attention span gone. |
| Mention mock agent | The agent is deterministic. The judge doesn't need to know that yet. Save for Q&A. |
| Show Architecture Book | A document is not a demo. Show the running system. |
| Explain SUSPENDED→ARCHIVED | It's unreachable and irrelevant to the demo arc. |

---

## Implementation Note

The entire opening can be delivered with:

1. **No backend changes** — the API already returns all 10 fields
2. **No demo.py changes** — the demo order is just reordered narration, not reordered code
3. **One command** — `python -c "..."` with three `requests.post` calls (or the actual `demo.py --auto` running in advance to pre-populate state)
4. **One pre-opened browser tab** — SigNoz trace #4 (or a screenshot as fallback)

**The only thing that changes is the narrative order and what you point at first.**
