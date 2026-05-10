# Sentinel AI — User Manual

Audience: anyone who logs into the Sentinel dashboard. For a high-level explanation of what the platform is and how the modules fit together, read [`PLATFORM_OVERVIEW.md`](./PLATFORM_OVERVIEW.md) first.

---

## Table of contents

1. [Logging in](#1-logging-in)
2. [Navigating the dashboard](#2-navigating-the-dashboard)
3. [Core](#3-core)
4. [Clinical Governance](#4-clinical-governance)
5. [Admin Governance](#5-admin-governance)
6. [Financial](#6-financial)
7. [Regulatory](#7-regulatory)
8. [Risk](#8-risk)
9. [Settings](#9-settings)
10. [Common tasks (cookbook)](#10-common-tasks-cookbook)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Logging in

1. Open `http://localhost:3000` (development) or your organization's Sentinel URL.
2. Enter your username and password. The default admin account on a fresh install is `admin` / `admin123` — change this in production.
3. On success you land on the **Dashboard**. The left-hand navigation shows only the sections your role can see.

### Session

- The JWT lives in `localStorage`; it auto-refreshes on 401 and you'll be redirected to login if refresh fails.
- Click your avatar (top-right) → **Logout** to sign out manually.
- **Restart product tour**: avatar menu → "Restart tour". The walkthrough overlay reintroduces each section.

### Theme

- Top-bar sun/moon icon toggles light/dark.

---

## 2. Navigating the dashboard

The left rail groups pages into sections. Sections you cannot access are hidden — your view depends on your role:

| Section | Roles that see it |
|---|---|
| Core | All authenticated users |
| Clinical Governance | system_admin, admin, cmio, data_scientist, clinical_user |
| Admin Governance | system_admin, admin, compliance_officer |
| Financial | system_admin, admin, compliance_officer |
| Regulatory | system_admin, admin, data_scientist, compliance_officer |
| Risk | system_admin, admin, cmio, data_scientist, compliance_officer |
| Settings | system_admin, admin |

If a section feels missing, ask an admin to confirm your role.

### Layout primitives

- **Tables** sort by clicking column headers and paginate at the bottom.
- **Filters** appear above tables — they update the URL so the view is shareable/bookmarkable.
- **Severity chips** are colored consistently: green = healthy, amber = attention, red = action required.
- **Empty states** explain *why* there's no data and what to do next, rather than showing a blank table.

---

## 3. Core

### 3.1 Dashboard (`/`)

The landing page. Live counters and trend charts:

- **Agents online** — agents that pinged within the heartbeat window.
- **Blocked actions (24h)** — policy decisions of `BLOCK` for the last day.
- **Open alerts** — alerts that have not been acknowledged.
- **Estimated financial impact** — dollar value of blocked actions, computed from policy metadata.

Metrics push over WebSocket, so you do not need to refresh.

### 3.2 Agents (`/agents`)

Inventory of every agent the SDK has ever phoned home from.

- The list shows agent ID, owner, last-seen timestamp, status, and recent block count.
- Click a row to open **Agent Detail** (`/agents/:agentId`):
  - **Overview** — config, owner, version, environment.
  - **Activity** — chronological feed of actions and policy decisions.
  - **Policies matched** — which policies fired against this agent and how often.

### 3.3 Policies (`/policies`)

Author and manage runtime rules.

- **Create**: top-right **+ New Policy** opens the policy editor.
  - Choose effect (`ALLOW`, `BLOCK`, `REQUIRE_REVIEW`, `LOG_ONLY`).
  - Define matchers (agent tags, action types, regex on action payloads).
  - Save → policy is live within seconds for new evaluations.
- **Edit / disable** an existing policy from the row's action menu.
- **Order matters**: policies evaluate top-to-bottom; the first match wins. Drag to reorder.

> **Tip:** start in `LOG_ONLY` mode for a few days to validate the matcher before flipping to `BLOCK`.

### 3.4 Audit Logs (`/audit`)

Every policy decision, with full context, persisted indefinitely (subject to retention policy).

- Filter by date range, agent, policy, decision, or free-text on payload.
- Click a row for the full evaluation: input, matched policy, decision, latency.
- **Export CSV**: filtered view → top-right **Export** button. Required for HIPAA audits.

### 3.5 Alerts (`/alerts`)

Two tabs:

- **Live** — unacknowledged alerts, highest severity first.
- **History** — everything, including acknowledged.

Acknowledge an alert by selecting it and clicking **Acknowledge**; a comment is required. Alerts are generated from alert *rules* — manage those at `/alerts/rules` (admin/analyst only).

### 3.6 Users (`/users`) *(admin/system_admin only)*

- **Create user**: choose username, email, role, optional organization.
- **Reset password**: row menu → **Reset password** generates a one-time link.
- **Deactivate**: toggling `is_active` revokes the user's tokens and prevents login without deleting their audit history.

---

## 4. Clinical Governance

### 4.1 Model Cards (`/clinical/model-cards`)

Documentation for every AI model used in patient care.

- **Lifecycle stages**: `draft` → `under_review` → `published` → `retired`. Only `published` is visible on the patient-facing Transparency Portal.
- **Auto-fill**: in the editor, **Auto-fill from GitHub/MLflow** populates intended use, training data, and metrics. Requires `GITHUB_TOKEN` and `MLFLOW_TRACKING_URI` configured server-side.
- **Publish** is gated on a passing Bias Audit younger than 90 days. The button is disabled with an explanation if the gate fails.
- **Versioning**: editing a published card creates a new version; the prior version is preserved for audit.

### 4.2 Bias Audits (`/clinical/bias-audits`)

Subgroup fairness analysis.

- The list shows audit ID, model, status, date, and headline metrics (demographic parity ratio, equalized-odds gap, disparate impact).
- Click a row for **Bias Audit Detail**:
  - Per-subgroup AUC and false-positive/negative rates.
  - Pass/fail per metric vs. configured thresholds.
  - Evidence: dataset reference, sample size, audit code version.
- **Run a new audit**: from the model card or list, **+ Run audit** queues a job that uses the model's registered test dataset.

### 4.3 Drift Monitor (`/clinical/drift`)

- Top: heatmap of all monitored models × time, colored by drift severity.
- Click a model → time-series of population-stability index (PSI), KL divergence, and prediction distribution.
- Drift breaches automatically open an alert and may trigger a HITL review depending on policy.

### 4.4 HITL Queue (`/clinical/hitl`)

Human-in-the-loop reviews.

- Each item is an AI output that policy flagged `REQUIRE_REVIEW` (or that drift/bias triggered).
- Review item → **Open** to see the full input, the AI output, and the recommended action.
- Decisions: **Approve**, **Override** (provide an alternative), or **Escalate**. All decisions are logged and feed the Risk score.

> **Clinical users:** focus on accuracy of the output, not the model. Use **Escalate** if you suspect a systemic issue rather than a one-off edge case.

---

## 5. Admin Governance

### 5.1 Shadow AI (`/admin/shadow-ai`)

Detection of unsanctioned AI tool use.

- Each row: timestamp, tool detected (e.g., ChatGPT, Claude.ai, Gemini), the staff member's IP, HIPAA risk band, severity, and allowlist status.
- **Allowlist** an entry when it is sanctioned (e.g., your IT-approved enterprise GPT). Allowlisted entries no longer raise alerts.
- **Investigate** opens a modal with the URL/domain history and any PHI patterns matched.

> If you see `08/05/2026 — — NO Active` blank rows, your detector hasn't ingested data yet — see Troubleshooting §11.

### 5.2 Scribe Audits (`/admin/scribe-audits`)

Periodic accuracy audits of AI ambient-scribe transcripts.

- Each audit compares the AI transcript against the clinician's final note.
- Metrics: hallucination rate, omission rate, PHI handling correctness, structured-data extraction accuracy.
- Click a row to see specific findings with severity.

### 5.3 Transparency Portal (`/transparency`)

The patient-facing list of AI in your organization.

- Inside the dashboard this page is the **author's view**. The **public** URL is generated when the page is published and given to your communications team.
- Each entry mirrors a published Model Card with the patient-friendly fields only (intended use, evidence base, oversight).
- The **View** action opens the patient-facing rendering in a dialog (it does *not* navigate away to the dashboard).

---

## 6. Financial

### 6.1 Prior Auth Trail (`/finance/prior-auth`)

Per-decision trail for AI-assisted prior authorizations.

- Filter by member, payer, status, or date.
- Click a row for: model used, model version, inputs the model saw, output, override (if any), final disposition, and the staff member who signed off.
- **Export** the filtered view for a payer dispute.

### 6.2 Revenue Cycle (`/finance/revenue-cycle`)

Same shape as prior auth, applied to claims scrubbing, code suggestions, and denial-management automations. The **Findings** column shows discrepancies between AI suggestion and final action — counts here drive the dashboard's "AI-flagged anomalies" tile.

---

## 7. Regulatory

### 7.1 Technical Files (`/regulatory/technical-files`)

EU MDR / FDA-style documentation packets per device.

- Each file aggregates: model card, bias audits, drift records, PMS reports, adverse events, training data summary.
- **Generate** triggers an auto-population pass; you then review and lock the file.
- A locked file is what you would hand to a notified body or auditor.

### 7.2 Adverse Events (`/regulatory/adverse-events`)

Capture and triage of reportable events.

- **+ New event** opens a structured form (event type, severity, model involved, narrative).
- Triage status flows `received` → `under_review` → `reportable` / `not_reportable` → `closed`.
- Reportable events feed the next PMS report automatically.

### 7.3 Post-Market Surveillance (`/regulatory/pms-reports`)

Periodic Safety Update Reports.

- The list shows draft and locked reports per device per period.
- **Generate PSUR** queues an auto-draft from the rolling reporting window. The auto-generator pulls from adverse events, drift, bias, and HITL outcomes.
- Edit the draft, attach signatures, then **Lock** for filing.

> The **Generate PSUR** action requires the device to have an `mdr_class` set on its model card. If you see a 405, your dashboard build is older than the backend route — refresh.

---

## 8. Risk

### 8.1 Risk Portfolio (`/risk/portfolio`)

A single, prioritized view of model risk across the organization.

- The score is a weighted blend of bias, drift, criticality, and incident history. Weights are configured in **Settings → Risk Config**.
- Sort by score; click a model to open **Risk Score Detail** (`/risk/scores/:modelId`).
- Detail page breaks the score into its four components and shows a 90-day trend so you can see whether the risk is rising or falling.

---

## 9. Settings

*(visible to admin / system_admin only)*

### 9.1 Organization (`/settings/organization`)

- Name, logo, default timezone, regional settings.
- Two-letter region code drives MDR/FDA defaults.

### 9.2 Risk Configuration (`/settings/risk`)

- Weights for bias, drift, criticality, incident contributions to the risk score.
- Thresholds for green/amber/red bands. Changes take effect on the next risk recompute (default: hourly).

### 9.3 HIPAA Configuration (`/settings/hipaa`)

- PHI redaction patterns (regex + named entities).
- Breach-notification contacts.
- Allowlists for shadow-AI detection.

---

## 10. Common tasks (cookbook)

### Onboard a new model end-to-end

1. ML team registers it in MLflow (or you create a model card directly).
2. **Clinical Governance → Model Cards → +**. Click **Auto-fill** to seed metadata.
3. Trigger a **Bias Audit** from the card. Wait for it to complete and pass thresholds.
4. **Publish** the card.
5. Confirm it appears on **Transparency Portal**.
6. Wire `@secure_agent` into the production code path.
7. Confirm the agent appears under **Agents** within minutes of first call.

### Investigate a real-time block

1. **Alerts** → click the new alert → note the `audit_log_id`.
2. **Audit Logs** → search the ID → review the matched policy and inputs.
3. If the block was a false positive: edit the policy or, more conservatively, add a narrower **ALLOW** above it.

### Respond to a payer dispute on a prior auth

1. **Financial → Prior Auth Trail**, filter by member.
2. Open the disputed decision, **Export** the trail PDF.
3. Attach to the appeal.

### File the quarterly PMS

1. **Regulatory → Post-Market** for the device → **Generate PSUR**.
2. Review the draft. Add narrative for any "unexplained" trend the auto-draft flags.
3. **Lock**, attach signatures, file.

### Add a new user

1. **Users → + New user**.
2. Choose role (see §2 for what each role sees).
3. The new user receives an email with a one-time login link (in dev: copy the link from the response).

---

## 11. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Login fails immediately | Backend down or CORS misconfigured. Check `http://localhost:8000/docs` is reachable. |
| Sidebar section missing | Your role does not include it. Ask an admin. |
| Dashboard counters frozen | WebSocket disconnected. The page auto-reconnects; if not, refresh. |
| Model Cards page errors / blank | Older bug fixed in latest dashboard build (`ModelCardList.tsx:93` undefined `toLowerCase`). Pull latest and rebuild. |
| Revenue Cycle shows zero findings | Findings are derived from policy decisions; if no policies match those agents, no findings appear. |
| Shadow AI shows blank rows / dashes | Detector not yet ingesting. Confirm the shadow-AI ingestion job is running and that traffic-mirror logs are flowing. |
| `POST /v1/regulatory/pms-reports/generate-psur` returns 405 | Frontend is ahead of backend. Restart the backend after pulling. |
| Transparency "View" button navigates to dashboard | Old behavior — fixed; the action now opens an in-place dialog. Pull latest. |
| Policies page is empty for a real org | Policies are scoped per-organization; switching orgs (system_admin) or seeding policies is required. |
| `react-router` future-flag warning in console | Cosmetic; does not affect functionality. |

For anything not in this list, open `http://localhost:8000/docs` and try the corresponding API call directly — the response body usually identifies the issue.
