# EvoMind Observability — Confidence Model

## Model Selection: Beta-Bernoulli

The Beta-Bernoulli model is chosen for three reasons:

1. **Interpretability**: Every parameter maps directly to evidence counts. α = supporting evidence + prior, β = contradicting evidence + prior.
2. **Closed-form updates**: No iterative computation. Each update is O(1).
3. **Explainability**: The confidence score `α/(α+β)` is a simple ratio that any engineer can understand and verify in SigNoz.

### Rejected Alternatives

| Model | Reason for Rejection |
|---|---|
| Thompson Sampling | Designed for bandit problems with exploration/exploitation. Overkill for single-rule evaluation. Adds unnecessary stochasticity. |
| Neural network | Opaque. Violates explainability principle. Cannot be debugged in SigNoz. |
| Simple ratio (pass/fail) | No principled way to incorporate prior belief. Cannot express uncertainty with few observations. |
| Heuristic weighted score | Arbitrary weights undermine reproducibility. No Bayesian foundation. |

---

## Mathematical Specification

### Prior

```
α₀ = 1.0
β₀ = 1.0
```

This is the Beta(1, 1) distribution — the uniform prior (also known as the Bayes-Laplace prior). It assigns equal density to all possible values of θ (the true underlying probability that the rule is beneficial).

Prior mean: `α₀ / (α₀ + β₀) = 0.5`

Rationale: Before any observations, we have no information about whether the rule will be effective. A uniform prior reflects this ignorance. The equivalent prior sample size is 2 (α₀ + β₀), which is weakly informative — it takes approximately 2 observations to meaningfully move confidence away from 0.50.

---

### Posterior Update

After each observation:

**Supporting evidence** (rule was needed or rule worked):
```
α ← α + 1
β ← β
```

**Contradicting evidence** (rule was not needed or rule failed):
```
α ← α
β ← β + 1
```

**Neutral evidence** (ambiguous classification):
```
No update.
```

**Baseline evidence** (safe SQL before rule promotion):
```
No update.
```

Baseline observations record that the agent produced safe SQL before the rule was enforced. They do NOT update α or β because they do not speak to the rule's effectiveness — the agent was not yet following the rule, it was acting independently.

---

### Confidence Calculation

```
Confidence = E[Beta(α, β)] = α / (α + β)

Variance = (α * β) / ((α + β)² * (α + β + 1))
```

Confidence is the expected value of the posterior distribution. It represents the system's belief that the rule is beneficial (i.e., that following it produces safe SQL).

---

### Edge Cases

| Scenario | α | β | Confidence | Interpretation |
|---|---|---|---|---|
| No observations | 1 | 1 | 0.50 | Complete uncertainty |
| All observations are supporting | 1+N | 1 | N+1 / N+2 → 1.0 | Confidence approaches 1.0 asymptotically |
| All observations are contradicting | 1 | 1+N | 1 / (N+2) → 0.0 | Confidence approaches 0.0 asymptotically |
| Equal supporting and contradicting | 1+N | 1+N | 0.50 | Maximum uncertainty regardless of N |
| Single supporting observation | 2 | 1 | 0.67 | Moderate confidence |
| Single contradicting observation | 1 | 2 | 0.33 | Moderate opposite confidence |
| All observations are baseline | 1 | 1 | 0.50 | Confidence unchanged — baseline has no effect |

---

### Asymptotic Behavior

```
lim(N_supporting → ∞) Confidence = 1.0
lim(N_contradicting → ∞) Confidence = 0.0
```

Confidence never reaches exactly 0.0 or 1.0 because α and β are always ≥ 1. This prevents division-by-zero and avoids overconfidence from finite evidence.

---

## Thresholds

| Threshold | Value | Rationale |
|---|---|---|
| `promotion_threshold` | 0.75 | Requires moderate-to-strong evidence. With prior, this requires ≈3 supporting observations with 0 contradicting, or ≈5 supporting with 1 contradicting. High enough to prevent noise-driven promotion. |
| `demotion_threshold` | 0.35 | Requires strong contradictory evidence to undo promotion. With prior, demoting from confidence=0.80 requires ≈4 consecutive contradictions. This prevents a single failure from immediately suspending a previously reliable rule. |
| `min_evidence` | 3 | Prevents promotion on 1–2 observations. Requires a minimum evidence base before the rule is trusted enough to inject. |

### Threshold Justification

The thresholds are asymmetric: promotion requires stronger evidence (0.75) than the symmetric midpoint, and demotion requires even stronger contradictory evidence (0.35, which is 0.40 away from promotion threshold). This creates hysteresis — the rule is "sticky" once promoted. This is intentional:

- **Promotion is cautious**: We only inject guidance when reasonably sure it will help
- **Demotion is conservative**: We don't suspend on a single bad request (which could be a transient LLM error)
- **Hysteresis prevents flapping**: The rule doesn't oscillate between Active and Suspended on each request

---

## Confidence History

The Confidence Engine maintains a time-series of confidence values via EvidenceRecord. Each record stores:

```json
{
  "evidence_type": "supporting",
  "confidence_before": 0.67,
  "confidence_after": 0.75,
  "delta": +0.08
}
```

This allows SigNoz to render a confidence-over-time chart and an engineer to identify exactly which observation caused which confidence change.

---

## Example Confidence Trajectory

| Request # | SQL | Classification | Evidence Type | α | β | Confidence | Δ |
|---|---|---|---|---|---|---|---|
| — | — | — | — | 1 | 1 | 0.50 | — |
| 1 | `SELECT * FROM users WHERE id = 123` | unsafe | supporting | 2 | 1 | 0.67 | +0.17 |
| 2 | `INSERT INTO orders VALUES (456, 'foo')` | unsafe | supporting | 3 | 1 | 0.75 | +0.08 |
| 3 | `UPDATE products SET price = 789 WHERE id = 1` | unsafe | supporting | 4 | 1 | 0.80 | +0.05 |

**After Request 3: confidence=0.80 >= 0.75, evidence=3 >= 3 → Rule promoted to Active**

| Request # | SQL | Evidence Type | α | β | Confidence | Δ |
|---|---|---|---|---|---|---|
| 4 | `SELECT * FROM users WHERE id = ?` | supporting | 5 | 1 | 0.83 | +0.03 |
| 5 | `INSERT INTO orders VALUES (?, ?)` | supporting | 6 | 1 | 0.86 | +0.03 |

---

## Update Algorithm (Pseudocode)

```
def update_confidence(rule, evidence_type):
    if evidence_type == "supporting":
        rule.alpha += 1
        rule.supporting_count += 1
    elif evidence_type == "contradicting":
        rule.beta += 1
        rule.contradicting_count += 1
    elif evidence_type == "neutral":
        return  # no change
    elif evidence_type == "baseline":
        return  # no change — records safe pre-rule behavior without affecting confidence
    
    confidence_before = rule.confidence
    rule.confidence = rule.alpha / (rule.alpha + rule.beta)
    
    # Check thresholds
    if rule.should_promote():
        rule.status = "active"
        rule.promoted_at = now()
    elif rule.should_demote():
        rule.status = "suspended"
        rule.demoted_at = now()
    
    return ConfidenceUpdate(
        confidence_before=confidence_before,
        confidence_after=rule.confidence,
        delta=rule.confidence - confidence_before,
        status_change=previous_status != rule.status
    )
```

---

## Telemetry Fields

Each confidence update emits the following attributes on the `evomind.confidence.updated` span:

| Attribute | Type | Example |
|---|---|---|
| `rule.id` | string | `a1b2c3d4-0001` |
| `rule.name` | string | `use_parameterized_sql` |
| `rule.confidence.before` | float | `0.67` |
| `rule.confidence.after` | float | `0.75` |
| `rule.confidence.delta` | float | `0.08` |
| `rule.alpha` | float | `3.0` |
| `rule.beta` | float | `1.0` |
| `evidence.type` | string | `supporting` |
| `evidence.supporting_count` | int | `3` |
| `evidence.contradicting_count` | int | `1` |
