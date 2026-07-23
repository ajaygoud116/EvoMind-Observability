# EvoMind Observability — Executive Summary

## Product Definition

EvoMind Observability is a **debugger for AI behavioral learning**. It makes the learning lifecycle of an AI agent observable as a production system.

It is:
- An observability platform for *behavioral change*
- A transparent evidence-to-behavior pipeline
- A SigNoz-integrated debugger for learning lifecycles

It is NOT:
- An AI agent
- A memory system
- A RAG framework
- A vector database
- An autonomous continual learning platform
- An AGI attempt

## The Engineering Claim

> "The behavioral learning lifecycle of an AI agent can be represented as an observable production system."

We are not claiming autonomous learning. We are claiming that learning *can be made observable* — every evidence signal, confidence delta, and rule transition can be traced, queried, and investigated without reading source code.

## The Vertical Slice

One agent. One domain. One repeated mistake. One behavioral rule. One learning lifecycle. One observability pipeline.

| Dimension | Value |
|---|---|
| Agent | Secure SQL Assistant |
| Domain | SQL query generation |
| Mistake | String interpolation in SQL |
| Rule | "Use parameterized queries" |
| Lifecycle | Evidence accumulation → Confidence update → Rule promotion → Guidance injection → Behavior improvement |
| Observability | OpenTelemetry → SigNoz |

## How It Works

1. The agent receives a natural-language request and generates SQL
2. An Outcome Evaluator classifies the SQL as safe/unsafe/ambiguous
3. Each classification becomes an **Observation**
4. Observations accumulate as **Evidence** for/against a behavioral rule
5. Evidence updates the rule's **Confidence** score
6. When confidence crosses a threshold, the rule is **Promoted** to Active
7. On subsequent requests, Active rules are **Retrieved** and **Injected** as guidance
8. The agent generates improved SQL
9. Every step emits structured telemetry to SigNoz

## Observable Questions

After implementation, a SigNoz dashboard should answer:

- Was a behavioral rule available?
- Was it retrieved?
- Which rule?
- What confidence did it have?
- Was guidance injected?
- What SQL was generated?
- Was it safe?
- How was the observation classified?
- Did confidence increase or decrease?
- Did the behavioral rule change state?
- Why did behavior change?
- Which evidence caused the change?
- What contradictory evidence exists?

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11+ | OTel SDK, sqlparse, ecosystem |
| API framework | FastAPI | Async, OTel-native, OpenAPI |
| Storage | SQLite | Zero-dependency, ACID, sufficient for single slice |
| SQL parser | sqlparse | Mature, deterministic, multi-dialect |
| Telemetry SDK | OpenTelemetry Python | Industry standard, SigNoz-native |
| Observability backend | SigNoz (self-hosted, Docker) | OTel-native, open-source, ClickHouse-backed |
| Agent | Mock (deterministic) | Ensures reproducible demo; swap for real LLM later |

## Success Criteria

A judge should be able to investigate a behavioral change using **SigNoz alone**, without reading source code, and answer:

- Why did the behavior change?
- Which evidence caused it?
- Why was the rule trusted?
- Which observations support it?
- Which observations contradict it?
- Did behavior improve?
- If behavior regressed, why?
