# Hackathon Release Eligibility Audit

**Project:** EvoMind Observability
**Hackathon:** Agents of SigNoz (WeMakeDevs × SigNoz, Jul 20–26, 2026)
**Audit Date:** 2026-07-24
**Auditor Role:** Hackathon Judge / Release Engineer / DevOps Reviewer

---

## 1. Eligibility Checklist

| # | Requirement | Source | Status | Evidence |
|---|-------------|--------|--------|----------|
| 1 | GitHub repository with source code | Rules §5 | ✅ | Present |
| 2 | Working demo | — | ✅ | `demo.py` — auto/interactive modes, 6 requests, deterministic |
| 3 | SigNoz usage (required tech) | Rules §A2 | ✅ Deeply integrated | OTLP gRPC, 4 SigNoz services, 12 spans, 4 metrics, full telemetry pipeline |
| 4 | Foundry-based SigNoz install | Field Req §1 | ❌ CRITICAL | SigNoz deployed via custom `docker-compose.yml`; Foundry not used |
| 5 | `casting.yaml` in repo | Field Req §3 | ❌ CRITICAL | File does not exist |
| 6 | `casting.yaml.lock` in repo | Field Req §3 | ❌ CRITICAL | File does not exist |
| 7 | AI assistant usage declared | Rules §7 | ❌ HIGH | No disclosure found anywhere in repo |
| 8 | Tests pass | — | ✅ | 214/214 passed, 0 failures |
| 9 | Submission via form | Rules §6 | ❓ | Form may require additional items not listed on rules page |

---

## 2. Repository Inventory

### Source Code
- `evomind/` — 59 Python files across 11 subpackages
- `tests/` — 20 test files (214 tests, 92.73% coverage)
- `demo.py` — 366-line demo script

### Configuration & Deployment
- `pyproject.toml` — declares dependencies (no `[build-system]` table)
- `Dockerfile` — builds app container
- `docker-compose.yml` — 5 services: clickhouse, query-service, frontend, otel-collector, evomind
- `ops/otel-collector-config.yaml` — OTel collector configuration
- `ops/signoz-dashboard.json` — 10-panel SigNoz dashboard
- `.env` — runtime config (in `.gitignore`, not tracked)

### Documentation (top-level)
- `README.md` — main project description
- `DEMO.md` — step-by-step demo walkthrough
- `JUDGE_GUIDE.md` / `FINAL_JUDGE_GUIDE.md` — judge evaluation guides
- `OBSERVABILITY_GUIDE.md` — SigNoz investigation guide
- `TRACE_WALKTHROUGH.md` — trace anatomy
- `HACKATHON_SUBMISSION_AUDIT.md` — pre-submission verification
- `LICENSE` — MIT

### Documentation (`docs/` — 14 files)
Full architecture book, data models, state machines, confidence model, API contracts, telemetry model, testing strategy, demo plan, ADRs, deliverable documents.

### Screenshots
- `screenshots/` — **empty** (only `.gitkeep`)

### MISSING: `casting.yaml`, `casting.yaml.lock`
Neither file exists anywhere in the repository.

### MISSING: AI usage disclosure
No mention of AI assistant usage (ChatGPT, Copilot, Claude, etc.) in any file.

---

## 3. Foundry Compliance

**Hackathon Field Requirement #1:** "Install SigNoz using Foundry."
**Hackathon Field Requirement #3:** "Your repo must include the `casting.yaml` and `casting.yaml.lock`."

### Current State
The project uses a hand-written `docker-compose.yml` to deploy SigNoz services (ClickHouse, query-service, frontend, otel-collector) alongside the app. No Foundry artifacts exist.

### What Foundry Provides
Foundry (`foundryctl cast`) is SigNoz's official deployment tool. Given a `casting.yaml` (typically 8–15 lines), it:
1. Validates prerequisites (`foundryctl gauge`)
2. Generates deployment files into `pours/` (`foundryctl forge`)
3. Deploys the stack (`foundryctl cast` — gauge + forge + deploy)
4. Writes `casting.yaml.lock` recording the exact deployment state

A minimal `casting.yaml` for this project would look like:
```yaml
apiVersion: v1alpha1
kind: Installation
metadata:
  name: signoz
spec:
  deployment:
    flavor: compose
    mode: docker
```

### Impact
- Judges explicitly state they "may re-run Foundry against them to reproduce your deployment"
- Without these files, judges **cannot** reproduce the deployment as the rules intend
- The custom `docker-compose.yml` is a **different deployment mechanism** that is not what the rules require

### Resolution Path
1. Install Foundry: `curl -fsSL https://signoz.io/foundry.sh | bash`
2. Create `casting.yaml` with appropriate MCP and dashboard moldings
3. Run `foundryctl cast -f casting.yaml` to generate `casting.yaml.lock` and deploy
4. Commit both files to the repository
5. The SigNoz dashboard JSON (`ops/signoz-dashboard.json`) and OTel collector config (`ops/otel-collector-config.yaml`) should be imported into the Foundry-managed deployment

**⚠️ This is a CRITICAL submission blocker.**

---

## 4. `casting.yaml` Verification

**Status:** ❌ File does not exist

The hackathon Field Requirements explicitly state the repo "must include the `casting.yaml` and `casting.yaml.lock`". Neither file is present. This is a direct violation of a stated submission requirement.

---

## 5. `casting.yaml.lock` Verification

**Status:** ❌ File does not exist

Generated automatically by `foundryctl cast`. Cannot exist without `casting.yaml`.

---

## 6. SigNoz Usage Verification

| Aspect | Status | Evidence |
|--------|--------|----------|
| OpenTelemetry SDK | ✅ | `opentelemetry-sdk>=1.22.0`, `opentelemetry-api>=1.22.0` in pyproject.toml |
| OTLP exporter | ✅ | `OTLPSpanExporter(endpoint=..., insecure=True)` in `evomind/telemetry/exporter.py` |
| SigNoz endpoint | ✅ | Default `http://localhost:4317` (gRPC), configurable via `.env` |
| Traces | ✅ | 12 span names, all emitted in orchestrator pipeline |
| Metrics | ✅ | 4 metric instruments (Counter, 3 ObservableGauges) |
| Dashboards | ✅ | `ops/signoz-dashboard.json` with 10 panels |
| Documentation | ✅ | Full trace walkthrough, observability guide, judge guide |
| Screenshots | ❌ | `screenshots/` empty |
| Demo evidence | ✅ | `DEMO.md` walks through SigNoz investigation for all 6 judge questions |

**SigNoz is central to the project, not superficial.** Every lifecycle step emits OpenTelemetry spans and metrics. The entire demo is built around showing SigNoz traces and dashboards. The judge guide teaches judges to investigate root causes using SigNoz.

---

## 7. OpenTelemetry Verification

| Aspect | Status | Details |
|--------|--------|---------|
| TracerProvider | ✅ | `TracerManager.initialize()` — sets global provider |
| MeterProvider | ✅ | `MeterManager.initialize()` — sets global provider |
| Span names | ✅ | 12 total: `evomind.request`, `.rule.retrieval`, `.guidance.injection`, `.sql.generation`, `.sql.evaluation`, `.observation.created`, `.evidence.appended`, `.confidence.updated`, `.rule.state_change`, `.lifecycle.complete`, `.system.startup`, `.rule.created` |
| Metric instruments | ✅ | 4 total: `evomind.requests.total` (Counter), `.sql.safety.ratio` (ObservableGauge), `.rule.confidence` (ObservableGauge), `.rule.evidence.count` (ObservableGauge) |
| OTLP export | ✅ | gRPC to `localhost:4317`, `BatchSpanProcessor`, `insecure=True` |
| Resource attributes | ✅ | service.name, service.version, schema.version, rule.version, telemetry.version, deployment.environment |
| Telemetry reaches SigNoz | ✅ | pipeline: app → OTLP gRPC → otel-collector → ClickHouse → query-service → frontend |
| Docs match implementation | ✅ (recently corrected) | Confidence values, version numbers, span names, API response fields all aligned per DOCUMENTATION_CONSISTENCY_REPORT.md |

---

## 8. Submission Readiness

### What is ready
- ✅ Fully instrumented Python application with 214 passing tests
- ✅ Complete OpenTelemetry integration with OTel SDK, TracerProvider, MeterProvider, OTLP exporter
- ✅ Full telemetry pipeline reaching SigNoz (traces + metrics + dashboards)
- ✅ Deterministic demo script with auto and interactive modes
- ✅ 14 architectural/design documentation files
- ✅ Judge guide, observability guide, trace walkthrough
- ✅ Pre-submission audit completed internally
- ✅ 3 P0 bugs fixed and verified
- ✅ Documentation consistency verified against implementation
- ✅ MIT License

### What is missing or problematic
| Item | Severity | Reason |
|------|----------|--------|
| `casting.yaml` | **CRITICAL** | Required by hackathon Field Requirements #1 and #3. Judges cannot reproduce deployment. |
| `casting.yaml.lock` | **CRITICAL** | Required by hackathon Field Requirement #3. Generated artifact; missing because casting.yaml missing. |
| Foundry-based SigNoz install | **CRITICAL** | Field Requirement #1 mandates Foundry deployment. Custom docker-compose.yml does not satisfy this. |
| AI usage disclosure | **HIGH** | Rule #6 requires declaration of any AI assistant use. No disclosure found in README or any doc. |
| Screenshots | **MEDIUM** | `screenshots/` contains only `.gitkeep`. Significantly weakens judge guide and demo materials. |
| No `[build-system]` in pyproject.toml | **MEDIUM** | `pip install .` relies on implicit setuptools. May fail on some Python versions/build environments. |
| FastAPI `on_event` deprecation | **LOW** | 23 warnings in test output. Non-functional; cosmetic. |
| Demo confidence peaks at 0.83 (not 0.88) | **LOW** | Recently corrected in docs. The actual max is 0.83 after 6 demo requests. |

---

## 9. Critical Blockers

### Blocker #1 (CRITICAL): Missing `casting.yaml`

**Source:** Hackathon Rules, SigNoz Field Requirements §3
**Exact text:** "**Make your deployment reproducible.** Your repo must include the `casting.yaml` and `casting.yaml.lock`. Judges may re-run Foundry against them to reproduce your deployment."
**Current state:** No `casting.yaml` exists anywhere in the repository.
**Impact:** Judges cannot run `foundryctl cast -f casting.yaml` to reproduce the SigNoz deployment, as the rules explicitly state they may do. Additionally, without `casting.yaml` the project has no Foundry-based deployment at all (Field Requirement §1).
**Severity:** CRITICAL — stated mandatory inclusion.

### Blocker #2 (CRITICAL): Missing `casting.yaml.lock`

**Source:** Hackathon Rules, SigNoz Field Requirements §3
**Exact text:** Same as Blocker #1 — "Your repo must include the `casting.yaml` and `casting.yaml.lock`."
**Current state:** No `casting.yaml.lock` exists. Even if `casting.yaml` were present, the lock file is a generated artifact that must be committed after running `foundryctl cast`.
**Impact:** Judges cannot verify the exact deployment state that produced the demo output.
**Severity:** CRITICAL — stated mandatory inclusion.

### Blocker #3 (CRITICAL): SigNoz not installed via Foundry

**Source:** Hackathon Rules, SigNoz Field Requirements §1
**Exact text:** "**Install SigNoz using Foundry.** Foundry installs both SigNoz and its MCP server in one step. Follow the Foundry quickstart to get started."
**Current state:** SigNoz services (clickhouse, query-service, frontend, otel-collector) are defined directly in a hand-written `docker-compose.yml`. Foundry was not used. The `foundryctl` CLI is not referenced anywhere in the repository. The MCP server is not deployed.
**Impact:** The project does not comply with the mandatory deployment method. Judges expecting to use Foundry will find no Foundry artifacts. The custom Compose file is not a substitute.
**Severity:** CRITICAL — stated Field Requirement, not optional.

### Blocker #4 (HIGH, disqualification risk): No AI assistant usage disclosure

**Source:** Hackathon Rules, Agency Protocols §7
**Exact text:** "Use of AI assistants (ChatGPT, Copilot, etc.) is permitted but must be declared in your submission. Failure to disclose will result in disqualification."
**Current state:** No disclosure statement exists in any repository file (README, submission docs, code comments, etc.).
**Impact:** The rules are explicit: "Failure to disclose will result in disqualification." This is not a judging penalty — it is a disqualification condition.
**Severity:** HIGH — risk of disqualification per the published rules.

---

## 10. Recommended Actions

### Critical (before submission)
1. **Add AI usage disclosure** (Blocker #4 — HIGH, disqualification risk)
   Add a section to `README.md` (or a `AI_DISCLOSURE.md`):
   ```markdown
   ## AI Assistant Disclosure
   This project was developed with assistance from AI coding tools (including but not limited to Claude/opencode) for code generation, debugging, documentation, and audit. All AI-generated code was reviewed and tested before inclusion.
   ```

2. **Install Foundry and create `casting.yaml`** (Blocker #2 — CRITICAL)
   ```bash
   curl -fsSL https://signoz.io/foundry.sh | bash
   ```
   Create `casting.yaml` at repo root:
   ```yaml
   apiVersion: v1alpha1
   kind: Installation
   metadata:
     name: signoz
   spec:
     deployment:
       flavor: compose
       mode: docker
     mcp:
       spec:
         enabled: true
   ```

3. **Generate `casting.yaml.lock`** (Blocker #3 — CRITICAL)
   ```bash
   foundryctl cast -f casting.yaml
   ```
   This deploys SigNoz via Foundry and generates `casting.yaml.lock`. Remove SigNoz services from the existing `docker-compose.yml` since Foundry now manages them.

4. **Update deployment instructions in README.md**
   - Primary method: `foundryctl cast -f casting.yaml`
   - Keep the existing `Dockerfile` for the app service; update `docker-compose.yml` to depend on Foundry-managed services instead of defining them

### High (before submission)
5. **Add screenshots** to `screenshots/`:
   - SigNoz dashboard overview
   - Trace view showing 6 requests
   - Confidence-over-time chart
   - Evidence table
   - State change span

### Medium (recommended)
6. **Add `[build-system]` to `pyproject.toml`**:
   ```toml
   [build-system]
   requires = ["setuptools>=68"]
   build-backend = "setuptools.backends._legacy:_Backend"
   ```
7. **Regenerate `.env`** without tracked values and ensure it stays in `.gitignore` (it already is — verify no prior commits contain it).

### Low (nice to have)
8. Fix 23 FastAPI `on_event` deprecation warnings by migrating to lifespan handlers.
9. Add the SigNoz MCP server configuration to `casting.yaml` as recommended by Field Requirement #2.

---

## Summary

| Category | Status |
|----------|--------|
| Foundry Compliance | ❌ **CRITICAL FAILURE** — Missing `casting.yaml`, `casting.yaml.lock`, and Foundry deployment |
| SigNoz Usage | ✅ Excellent — Deeply integrated, OTLP gRPC, traces + metrics + dashboards |
| OpenTelemetry | ✅ Complete — 12 spans, 4 metrics, TracerProvider, MeterProvider, OTLP exporter |
| Repository Completeness | ⚠️ Good — All docs present, but screenshots empty |
| AI Disclosure | ❌ **HIGH FAILURE** — No disclosure statement |
| Reproducibility | ❌ **CRITICAL FAILURE** — Cannot reproduce via Foundry as rules require |
| Tests | ✅ 214/214 passed, 92.73% coverage |
| Documentation Consistency | ✅ Recently verified and corrected |

---

## FINAL VERDICT

❌ **NOT READY FOR SUBMISSION**

### Blocking Issues:

1. **CRITICAL** — `casting.yaml` does not exist (Field Requirements §3: "Your repo must include the `casting.yaml`")
2. **CRITICAL** — `casting.yaml.lock` does not exist (Field Requirements §3: "Your repo must include the ... `casting.yaml.lock`")
3. **CRITICAL** — SigNoz not installed via Foundry (Field Requirements §1: "Install SigNoz using Foundry")
4. **HIGH** — No AI assistant usage disclosure (Rules §7: "must be declared in your submission. Failure to disclose will result in disqualification")

These four issues must be resolved before the repository satisfies the published Agents of SigNoz hackathon submission requirements.
