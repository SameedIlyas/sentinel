# Sentinel AI — Platform Overview

**One-line:** Sentinel AI is a governance and compliance platform for healthcare AI — it inventories every model in your organization, enforces policy at runtime, and produces the audit trail your regulators, payers, and clinicians require.

---

## 1. What problem does Sentinel solve?

Healthcare organizations are deploying AI faster than they can govern it. The result is a familiar set of risks:

- **No single inventory** of where AI is being used (clinical decision support, ambient scribes, prior-auth automation, revenue-cycle agents, plus unsanctioned "shadow" tools that staff bring in).
- **No fairness baseline** — models may underperform for protected subgroups, exposing the organization to legal and reputational risk.
- **No drift alarm** — a model that worked at deployment can silently degrade as patient populations and data pipelines change.
- **No regulator-ready paper trail** for FDA, EU AI Act, MDR PSUR, HIPAA, and state attorney-general inquiries.
- **No human-in-the-loop checkpoint** for high-risk AI outputs that affect patient care or financial determinations.

Sentinel addresses each of these as a connected workflow rather than a stack of disconnected spreadsheets.

---

## 2. What it is, technically

Sentinel ships as two services running side-by-side:

| Component | Stack | Purpose |
|---|---|---|
| **Policy Engine** (`policy_engine/`) | FastAPI · SQLAlchemy · Alembic · APScheduler · PostgreSQL/SQLite | Stateless REST + WebSocket API. Owns evaluation, scheduling, persistence, and integrations (MLflow, FHIR, DICOM). |
| **Dashboard** (`dashboard/`) | React 18 · TypeScript · Vite · MUI 5 · React Router v6 | Browser app for clinicians, data scientists, compliance officers, and admins. JWT-authenticated, role-aware navigation. |
| **Sentinel SDK** (`sentinel/`) | Python | Drop-in `@secure_agent` decorator and `drift_logger` that production agents use to report telemetry to the Policy Engine. |

Background jobs — MLflow registry sync, drift recompute, post-market report auto-generation, risk recompute — run inside the Policy Engine via a scheduler registered at startup (`policy_engine/main.py:97`).

---

## 3. Module-by-module — what the platform has

The dashboard is organized into seven sections. Visibility is controlled by the user's role (see §5).

### 3.1 Core (all authenticated users)

| Page | What it does |
|---|---|
| **Dashboard** | Real-time metrics: agents online, blocked actions, alerts, financial impact. Charts powered by recharts; updates pushed via WebSocket. |
| **Agents** | Registry of every AI agent the SDK has ever phoned home from. Drill in for activity timeline, policy match history, and config. |
| **Policies** | Policy CRUD. Authors write rules (block/allow/require-review) that the engine evaluates at runtime against agent actions. |
| **Audit Logs** | Searchable, exportable log of every policy evaluation. Required for HIPAA §164.312 audit controls. |
| **Alerts** | Live alert feed with rule configuration and acknowledgement. |
| **Users** *(admin only)* | Create users, assign roles, deactivate accounts. |

### 3.2 Clinical Governance

| Page | What it does |
|---|---|
| **Model Cards** | Per-model documentation (intended use, training data, evaluation metrics, limitations, lifecycle stage). Optional MLflow auto-sync creates draft cards when ML registers a new model. |
| **Bias Audits** | Subgroup fairness analysis (demographic parity, equalized odds, AUC by cohort). Gates `model_card.publish` — a model with no recent passing audit cannot be promoted. |
| **Drift Monitor** | Population-stability index, KL divergence, and prediction drift over rolling windows. Ingests telemetry from the SDK's `drift_logger` and from periodic recompute jobs. |
| **HITL Queue** | Human-in-the-loop review queue. AI outputs flagged "require-review" by policy land here for a clinician/CMIO to approve, override, or escalate. |

### 3.3 Admin Governance

| Page | What it does |
|---|---|
| **Shadow AI** | Discovers AI tools staff use *outside* sanctioned channels (e.g., pasting PHI into a public LLM). Combines network telemetry with a tool taxonomy and HIPAA risk scoring. |
| **Scribe Audits** | Periodic accuracy/safety audits of AI ambient-scribe transcripts vs. clinician edits. Tracks hallucination rate and PHI handling. |
| **Transparency Portal** | Public-facing page (per organization) listing the AI a patient may encounter during their care. Required by some state laws and increasingly by payers. |

### 3.4 Financial

| Page | What it does |
|---|---|
| **Prior Auth Trail** | End-to-end trail of AI-assisted prior-authorization decisions — who/what decided, what the model saw, what was overridden. Useful when payers contest a denial. |
| **Revenue Cycle** | Same audit shape for AI used in claims scrubbing, coding suggestions, and denial-management automation. |

### 3.5 Regulatory

| Page | What it does |
|---|---|
| **Technical Files** | EU MDR / FDA-style technical documentation packets per device. Auto-populated from model cards, bias audits, drift records, and PMS data. |
| **Adverse Events** | Reportable event capture and triage. |
| **Post-Market Surveillance** | Periodic Safety Update Reports (PSUR) — auto-generated draft from the prior reporting period's data, then edited and signed off. |

### 3.6 Risk

| Page | What it does |
|---|---|
| **Risk Portfolio** | Aggregated, weighted risk score per model based on bias, drift, criticality, and incident history. Overview heatmap; click into a model for the score's components. |

### 3.7 Settings (admin only)

| Page | What it does |
|---|---|
| **Organization** | Org metadata, branding, regional settings. |
| **Risk Configuration** | Tunable weights for the risk score; thresholds for green/amber/red. |
| **HIPAA Configuration** | PHI redaction rules, breach-notification contacts, allowlists for shadow-AI scoring. |

---

## 4. What the platform does — end-to-end flows

The pages above only make sense as the surface of cross-module workflows. The two flows that matter most:

### 4.1 Model lifecycle (from registration to retirement)

```
ML team registers model in MLflow
        │
        ▼
[auto-sync job]  →  draft Model Card created, owner notified
        │
        ▼
Owner fills card → triggers Bias Audit (precondition for publish)
        │
        ▼
Bias Audit passes → Model Card published → Risk score computed
        │
        ▼
Production: SDK sends predictions → Drift Monitor + Audit Logs
        │
        ▼
Drift exceeds threshold → Alert + HITL queue + Risk score recomputed
        │
        ▼
Quarterly: Technical File & PMS report auto-drafted from rolling data
```

### 4.2 Real-time policy enforcement

```
Production agent calls @secure_agent(...)
        │
        ▼
SDK serializes the action and posts to /v1/policy/check
        │
        ▼
Policy Engine evaluates active policies for that org/agent
        │
        ▼
   ┌────────────┬──────────────┬──────────────────┐
   ▼            ▼              ▼                  ▼
 ALLOW       BLOCK         REQUIRE_REVIEW       LOG_ONLY
   │            │              │                  │
   ▼            ▼              ▼                  ▼
proceed     SDK raises     queued in HITL     audit log only
            PolicyBlock    (clinician decides)
        │
        ▼
Every outcome → Audit Log + Dashboard counter + (if breach) Alert
```

---

## 5. Who uses it — roles

Eight roles are defined in `dashboard/src/types/index.ts`. Navigation is filtered by role in `dashboard/src/config/navigation.ts`.

| Role | Typical user | Sees |
|---|---|---|
| `system_admin` | Sentinel platform admin | Everything, across orgs |
| `admin` | Hospital/system IT admin | Everything for one organization |
| `cmio` | Chief Medical Informatics Officer | Clinical governance + Risk + HITL |
| `data_scientist` | ML engineer / data scientist | Model Cards, Bias, Drift, Risk, Regulatory |
| `compliance_officer` | HIPAA / regulatory lead | Admin Governance, Financial, Regulatory, Risk |
| `clinical_user` | Physician, nurse, advanced practice | HITL Queue, Model Cards (read-only) |
| `analyst` | Security analyst | Audit Logs, Alerts, Agents |
| `viewer` | Read-only stakeholder | Read-only across permitted modules |

---

## 6. Integrations

| System | How it connects |
|---|---|
| **MLflow** | Hourly registry sync auto-creates draft model cards (`policy_engine/services/mlflow_auto_sync.py`). Configure with `MLFLOW_TRACKING_URI` and `MLFLOW_AUTO_SYNC=true`. |
| **GitHub** | Model card auto-fill pulls README + metadata when a card has a `github_repo_url`. Needs `GITHUB_TOKEN`. |
| **FHIR** | Read-only resource cache for clinical context (`/v1/fhir/*`). |
| **DICOM** | Metadata cache for imaging-AI workflows (`/v1/dicom/*`). |
| **WebSocket** | Real-time push for dashboard counters, alerts, and HITL queue updates. |
| **SDK telemetry** | Production agents use `from sentinel import secure_agent` and `sentinel.sdk.drift_logger` to phone home. |

---

## 7. Repository map

```
policy_engine/             FastAPI service (the API)
  routes/                  HTTP routes — grouped clinical/, admin/, finance/, regulatory/
  services/                Background jobs, business logic, integrations
  models/                  SQLAlchemy ORM
  middleware/              Auth, CSRF, rate-limiting, tenant-context
  domain/                  Pure-domain calculations (bias, shadow-AI scoring)

dashboard/                 React app (the UI)
  src/pages/               One folder per module (clinical, admin, finance, regulatory, risk, settings)
  src/components/          Layout, auth, common
  src/api/client.ts        Single Axios client; JWT in Authorization header
  src/config/navigation.ts Role-filtered navigation tree
  src/walkthrough/         First-run product tour

sentinel/                  Python SDK — used by customer agents
alembic/                   Database migrations
tests/                     pytest suite (backend + integration)
docs/                      Roadmaps and (this) overview/manual
seed_demo_*.py             Demo-data seeders (extended, healthcare)
```

---

## 8. Where to go next

- **First time running the platform?** → `QUICKSTART.md` at the repo root.
- **Day-to-day usage?** → `docs/USER_MANUAL.md`.
- **API reference?** → http://localhost:8000/docs (OpenAPI / Swagger UI) once the engine is running.
- **What's coming?** → `docs/ROADMAP_TIER2_AUTO_INGEST.md` and `docs/ROADMAP_TIER3_NO_DATA_SOURCE.md`.
