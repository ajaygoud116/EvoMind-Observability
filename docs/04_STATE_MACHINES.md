# EvoMind Observability — State Machines

## BehavioralRule State Machine

The behavioral rule progresses through a lifecycle as evidence accumulates and confidence changes.

### State Diagram

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    ▼                                      │
              ┌──────────┐     confidence >= threshold    │
              │ CANDIDATE │─────────── and ────────────────┤
              │           │     evidence >= min            │
              └──────────┘                                │
                    │                                      │
                    │ (on any evidence-bearing request)    │
                    │                                      │
                    ▼                                      │
              ┌──────────────────────────────────────────┐ │
              │               ACTIVE                     │◀┘
              │  (retrieved + injected on every request)  │
              └──────────┬───────────────────────────────┘
                         │
                         │ confidence < demotion_threshold
                         ▼
              ┌──────────────────┐
              │    SUSPENDED     │
              │ (not retrieved)  │
              └──────┬───────────┘
                     │
                     │ confidence >= promotion_threshold
                     │ (re-promotion possible)
                     │
                     ▼
              ┌──────────────────┐
              │     ACTIVE       │
              └──────────────────┘

  Any state ──→ ARCHIVED (manual / not auto-transitioned)
```

### States

| State | Label | Description | Retrieved? | Confidence Influence |
|---|---|---|---|---|
| Candidate | `candidate` | Initial state. Rule is defined. Evidence is being collected passively. Observations are recorded but the rule is not yet enforced. | No | Observations adjust confidence freely |
| Active | `active` | Rule has sufficient evidence and confidence. It is retrieved on every matching request and guidance is injected into the agent's prompt. | Yes | Supporting observations increase confidence; contradictions decrease it |
| Suspended | `suspended` | Rule was previously Active but accumulated sufficient contradictory evidence. It is no longer retrieved. Can be re-promoted if confidence recovers. | No | Observations still adjust confidence |
| Archived | `archived` | Terminal state. Rule is permanently retired. No further observations are recorded against it. | No | No |

### Transitions

| From | To | Condition | Side Effects |
|---|---|---|---|
| (initial) | Candidate | Rule is created and seeded into the registry | Emit telemetry span: `evomind.rule.created` |
| Candidate | Active | `confidence >= promotion_threshold` AND `supporting_count + contradicting_count >= min_evidence` | Set `promoted_at`. Emit `evomind.rule.state_change` with `{from: "candidate", to: "active", reason: "confidence_threshold_met"}` |
| Active | Suspended | `confidence < demotion_threshold` | Set `demoted_at`. Emit `evomind.rule.state_change` with `{from: "active", to: "suspended", reason: "confidence_below_demotion_threshold"}` |
| Suspended | Active | `confidence >= promotion_threshold` | Set `promoted_at`. Emit `evomind.rule.state_change` with `{from: "suspended", to: "active", reason: "re_promoted"}` |
| Any | Archived | Manual operation via administrative API | Emit `evomind.rule.state_change` with `{from: "<current>", to: "archived", reason: "manual"}` |

### Transition Entry Criteria (Detailed)

**Candidate → Active**

| Criterion | Value | Rationale |
|---|---|---|
| `confidence >= promotion_threshold` | >= 0.75 | High confidence that the rule is needed/effective |
| `total_evidence >= min_evidence` | >= 3 | Prevents promotion on a single observation |
| `status == "candidate"` | | Must be in correct source state |

**Active → Suspended**

| Criterion | Value | Rationale |
|---|---|---|
| `confidence < demotion_threshold` | < 0.35 | Strong contradictory evidence has accumulated |
| `status == "active"` | | Must currently be active |

### Failure Conditions

| Scenario | Behavior |
|---|---|
| Confidence is NaN | Treat as 0.0. Emit warning span event. Do NOT transition. |
| Evidence count overflow | Cap at 1e6. Confidence approaches 0.0 or 1.0 asymptotically. |
| Race condition on concurrent requests | SQLite serializes writes. Confidence update is atomic. Each request sees a consistent snapshot. |
| Rule deleted while Active | Orchestrator catches NotFound and skips retrieval. Emit error span event. |

### State Machine Enforcement

The BehavioralRuleRepository enforces state transitions. No component other than the repository may change `status` directly. The Confidence Engine requests a transition check after each update, but the repository makes the final decision.

```
ConfidenceEngine.update(rule_id)
  → new_confidence
  → returns: UpdateResult { confidence, should_check_transition: true }

Orchestrator calls:
  → rule_repository.check_transition(rule_id)
  → returns: TransitionResult { transitioned: bool, from_status, to_status }
```

### State Visibility in Telemetry

Every state transition is its own span:

`evomind.rule.state_change`

| Attribute | Example |
|---|---|
| `rule.id` | `a1b2c3d4-0001` |
| `rule.name` | `use_parameterized_sql` |
| `rule.status.from` | `candidate` |
| `rule.status.to` | `active` |
| `rule.confidence` | `0.80` |
| `transition.reason` | `confidence_threshold_met` |
| `evidence.supporting_count` | `4` |
| `evidence.contradicting_count` | `1` |

Additionally, every request traces the current state as a span attribute on the root span:
- `rule.status` — current status at request time
- `rule.retrieved` — whether a rule was retrieved
