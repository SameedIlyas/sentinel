# Tier 2 Roadmap — Pages That Could Move from Manual to Automatic Ingestion

These pages all have **complete CRUD backends** and the data they hold is real and useful. The gap is that today every row exists because a human typed it in (or the seeder generated it). Each one has a *concrete trigger point* in the existing system where data could be auto-created — turning "fill out a form" into "show up automatically when X happens."

For each: **what it costs to add auto-ingest** and **what users gain** when we do.

---

## 1. Model Cards (`/clinical/model-cards`)

### Today
HUMAN_ENTRY: someone manually fills out 12 fields per model card. Phase 4 work added an `auto-fill` button that pulls from GitHub README + MLflow metrics, but the user must click it AND configure `GITHUB_TOKEN` + `MLFLOW_TRACKING_URI`.

### Auto-ingest opportunity
Every model registered in MLflow → auto-create a draft model card.

### How
1. Add `MLFLOW_AUTO_SYNC=true` env var
2. Background job (APScheduler `IntervalTrigger`, 1 hour) calls MLflow REST API `GET /api/2.0/mlflow/registered-models/list`
3. For each registered model not in our DB:
   - Create draft model card with `name`, `version`, `intended_use=""`, `lifecycle_stage="draft"`
   - Run existing auto-fill against the GitHub repo URL (if set in MLflow tags)
   - Create a `clinical_user_action_required` notification for the model owner
4. On model registry version bump → auto-create new `ModelCardVersion` row

### Effort
- Background sync job + MLflow client: 3 days
- Notification system + owner detection: 2 days
- Tests: 1 day

### User benefit
- ML team registers a model in MLflow → governance team sees it the same hour, not "after the next compliance audit"
- Eliminates the drift between "what we have in production" and "what is documented"
- Establishes governance gate: a model with no card (or a draft card) cannot reach `lifecycle_stage=published` without a CMIO review

### Trigger point in codebase
Model registration happens in MLflow; we just poll. No code change to existing endpoints needed.

---

## 2. Bias Audits (`/clinical/bias-audits/{id}`)

### Today
CRUD only. The `/run` endpoint creates a row but doesn't actually compute fairness — would need a real bias library wired in.

### Auto-ingest opportunity
**Two triggers:**

(a) **On model card publish** → auto-create a "Pending bias audit" row that blocks publication until it completes.
(b) **On test-set ingestion** → if a model has a test dataset registered, run the audit on a schedule (monthly).

### How
1. Wire `policy_engine/services/bias_auditor.py` to use [Fairlearn](https://fairlearn.org/v0.10.0/api_reference/index.html) (Python lib, Apache 2.0):
   ```python
   from fairlearn.metrics import demographic_parity_ratio, equalized_odds_ratio
   ```
2. Add `BiasAuditDataset` table — references to test datasets stored in S3/local with subgroup labels
3. New endpoint `POST /v1/clinical/bias-audits/{id}/run` that:
   - Loads dataset
   - Calls model's prediction endpoint
   - Computes per-subgroup AUC, demographic parity, equalized odds, disparate impact ratio
   - Writes `BiasAuditSubgroup` + `BiasAuditResultModel` rows
4. Hook into model card publish flow: rejects publish if no completed audit < 90 days old

### Effort
- Fairlearn integration + dataset loader: 1 week
- Auto-trigger on publish: 2 days
- Scheduled re-audit job: 2 days
- Audit-blocks-publish flow: 3 days

### User benefit
- Model governance moves from honor system to gate: you cannot publish a model card without a clean fairness audit
- Drift in fairness over time becomes visible (each scheduled audit shows trend)
- Regulatory artifact for FDA/state attorneys-general inquiries comes free

### Trigger point in codebase
- `policy_engine/routes/clinical/model_cards.py` — `publish_model_card` endpoint (~line 230). Add bias-audit precondition check.
- New scheduled job in `policy_engine/main.py` lifespan.

---

## 3. Drift Monitor (`/clinical/drift`)

### Today
CRUD only. Drift baselines and measurements must be POSTed manually; no upstream pipeline writes them.

### Auto-ingest opportunity
**Streaming inference logs from ML inference endpoint → continuous drift measurement.**

### How
1. Add a Sentinel SDK helper for inference servers:
   ```python
   from sentinel.sdk import drift_logger
   drift_logger.log_inference(model_id="mc_sepsis", features=X, prediction=y_pred, latency_ms=14)
   ```
2. SDK batches and POSTs to new `POST /v1/clinical/drift/log-batch` endpoint (1000 records/batch, 60s interval)
3. Background job (every 6 hours) computes:
   - Population Stability Index (PSI) per feature vs baseline
   - Kolmogorov-Smirnov test on numeric features
   - Performance shift (using ground-truth labels lagged 7 days)
4. Auto-creates `DriftAlert` rows when PSI > 0.2 or KS p-value < 0.01

### Effort
- SDK drift logger + batching: 1 week
- Server batch endpoint: 3 days
- Drift computation job (`scipy.stats`): 1 week
- Alerting threshold UI: 2 days

### User benefit
- ML platform team currently has no visibility into "is my deployed model still calibrated?" Sentinel becomes that observability layer
- When a population shifts (e.g., flu season changes admission patterns), the team sees it within a day, not a quarter
- Drift alerts auto-create HITL reviews (see #4) — the governance loop closes itself

### Trigger point
- New SDK module + new POST endpoint
- Existing `/v1/clinical/drift/measure` endpoint extended to accept batch payloads

---

## 4. HITL Queue (`/clinical/hitl`)

### Today
CRUD only. Reviews are manually created. Today's seed produces 6 examples; in production, the queue is empty.

### Auto-ingest opportunity
**Already 90% wired** — the policy engine supports `action: require_approval`. We just don't seed any policies that USE it.

### How (1 sprint)
1. Update `seed_demo_data.py` so 1-2 demo policies use `action: require_approval` (e.g. "transactions $1k–$10k")
2. In `policy_engine/routes/policy_check.py`: when a check returns `decision=APPROVED` (the existing "requires approval" path), auto-create a `HITLReview` row with:
   ```python
   HITLReview(
       title=f"Approval needed: {tool_name} by {agent_name}",
       description=audit_log.reason,
       ai_decision={"recommendation": "block", "confidence": ...},
       risk_score=_compute_risk_from_audit(audit_log),
       status="pending",
       priority=_priority_from_severity(audit_log),
       sla_deadline=now + timedelta(hours={"urgent":4,"high":24,"medium":72}[priority])
   )
   ```
3. Drift alerts (#3) and bias audit failures (#2) also auto-create HITL reviews

### Effort
- Wiring code: 4 hours
- Seed updates: 1 hour
- Tests: 4 hours
- Total: 1 day

### User benefit
- The "require human approval" feature in policies actually does something visible (today it just sets a status)
- Reviewers have a queue; SLAs become measurable; escalations work
- Audit trail of approvals satisfies HIPAA "minimum necessary" review requirements

### Trigger point
`policy_engine/routes/policy_check.py` — the `trigger_alert()` already runs after policy decisions. Add a `trigger_hitl()` companion call when decision is APPROVED.

---

## 5. Transparency Portal (`/transparency`)

### Today
Manual entry. Each transparency record (plain-language summary of what an AI does, intended population, limitations) is written by hand.

### Auto-ingest opportunity
**On model card publish** → auto-generate a transparency record draft using the model card's intended_use, indications, contraindications.

### How
1. On `POST /v1/clinical/model-cards/{id}/publish`: also create a `TransparencyRecordModel` row populated from the card
2. Use Claude Haiku to translate the technical fields into plain-language summary:
   ```python
   prompt = "Rewrite this clinical AI model description for a patient audience at 8th-grade reading level: {intended_use} {indications}"
   ```
3. Mark as "draft" — requires human review before publication (compliance officer signs off)
4. On every `ModelCardVersion` creation: bump the `TransparencyVersion`

### Effort
- Publish-hook code: 3 days
- LLM-based plain-language summarizer: 2 days
- Compliance officer review UI: existing (just needs a "needs review" filter)

### User benefit
- 21st Century Cures / ONC HTI-1 mandate: AI used in clinical decisions must have a public-facing transparency record. Today this is manual + late. Auto-draft makes it on-time and consistent.
- Reduces compliance officer work from "write 12 docs" to "review 12 drafts"
- Patient-portal integration becomes feasible (the summary is structured, not free-form)

### Trigger point
Model card publish endpoint already exists; just add a service call.

---

## 6. Technical Files (`/regulatory/technical-files`)

### Today
HUMAN_ENTRY. Regulatory team uploads sections one-by-one for FDA 510(k) or EU MDR submissions.

### Auto-ingest opportunity
**Templating + auto-population** from existing sources.

### How
1. Define section templates per regulatory type:
   - `fda_510k`: device_description, intended_use, performance_data, risk_management, clinical_evaluation, predicate_comparison
   - `eu_mdr`: same plus clinical_post_market_plan, clinical_evidence
2. On Technical File creation, auto-populate sections:
   - `device_description`, `intended_use` ← model card
   - `performance_data` ← MLflow metrics + linked bias audit results
   - `risk_management` ← linked risk score + adverse events list
   - `clinical_evaluation` ← linked PMS reports
3. Mark `auto_generated=True` so reviewers know what to verify
4. Quarterly sync: when underlying data changes (new bias audit, new adverse event), prompt the file owner to re-version

### Effort
- Template engine: 1 week
- Auto-population logic: 1 week  
- Re-sync notification: 3 days

### User benefit
- 510(k) submission today = months of cross-referencing; auto-population makes it days
- Single source of truth: model card is updated → tech file auto-updates the relevant section
- FDA Q-Sub responses become regenerable

### Trigger point
- Existing `POST /v1/regulatory/technical-files` extended with `auto_populate=true`
- New webhook on model_card update → "tech file XYZ may need re-versioning"

---

## 7. Post-Market Surveillance (`/regulatory/pms-reports`)

### Today
Reports generated only when someone clicks "Generate PSUR" button.

### Auto-ingest opportunity
**Scheduled report generation** for required regulatory cadences.

### How
1. APScheduler job in `policy_engine/main.py` lifespan:
   ```python
   scheduler.add_job(generate_quarterly_pms, 'cron', month='1,4,7,10', day=1, hour=2)
   scheduler.add_job(generate_psur, 'cron', month=1, day=1, hour=2)  # annual
   ```
2. Each scheduled run calls existing `pms_reports.py:generate_report()` with computed period, then **saves as draft** for compliance officer review
3. Auto-include:
   - Adverse event count + severity breakdown (from `adverse_events`)
   - Drift alert count (from `drift_alerts`)
   - Decision volume (from `audit_logs`)
   - Bias audit results delta vs prior period

### Effort
- Scheduled job + period computation: 3 days
- LLM-generated executive summary section: 3 days
- Compliance review queue: 2 days

### User benefit
- EU MDR PSUR is mandatory annually; FDA MAUDE-equivalent reports quarterly. Manual generation = late filings + fines. Auto = on time + consistent.
- Trend analysis across periods becomes possible (Q1→Q2→Q3 metric deltas)

### Trigger point
New APScheduler job; existing report-generation logic untouched.

---

## 8. Risk Portfolio (`/risk/portfolio`)

### Today
Risk scores must be POSTed manually for each model. The page shows whatever has been computed.

### Auto-ingest opportunity
**Daily risk recomputation** for every model based on the latest signal.

### How
1. APScheduler job daily at 02:00:
   ```python
   for model_card in db.query(ModelCard).filter_by(lifecycle_stage="published").all():
       severity = compute_severity(model_card)  # from bias_audit + adverse_events
       exposure = compute_exposure(model_card)  # from audit_logs (decision volume) + agent count
       reg_penalty = compute_reg_penalty(model_card)  # from regulatory_flags
       risk_score = create_risk_score(model_card.id, severity, exposure, reg_penalty)
   ```
2. Severity inputs (already available):
   - Patient safety: from latest `AdverseEvent` (severity weighted)
   - Bias magnitude: from latest `BiasAudit` max disparity ratio
   - Drift magnitude: from latest `DriftMeasurement` magnitude
   - Model confidence: from `ModelCard.performance_metrics`
3. Exposure inputs:
   - Patient volume: count of distinct patients in audit logs (when patient_id available)
   - Decision frequency: audit_log count last 30 days
   - Automation level: ratio of decisions made without human review

### Effort
- Score-recompute job: 1 week
- Factor extractors: 1 week
- Trend alerting (if delta > threshold, fire alert): 3 days

### User benefit
- "Which model is currently most risky to our org" becomes a live metric, not a quarterly review
- When a new bias audit fails or a drift alert fires, the affected model's risk score updates within 24h
- Board-level reporting: "we have 17 production models, 2 are critical risk, here's why" is one query, not a spreadsheet

### Trigger point
New APScheduler job; existing scoring logic in `policy_engine/domain/regulatory/risk_scoring.py` untouched.

---

## Cross-Cutting Pattern

Notice all 8 pages share the same architecture:
1. Static seed data → looks fine in demo
2. Manual CRUD → works for governance teams who like spreadsheets
3. **Event-triggered ingestion** ← what we'd add to make it real
4. Background recomputation jobs ← what closes the loop

The work order matters:

| Sprint | Ship |
|---|---|
| **Sprint 1** | #4 (HITL auto-create — already wired, just needs the connection) — 1 day; #5 (Transparency draft on publish) — 1 week |
| **Sprint 2** | #1 (Model card MLflow sync) — 1 week; #8 (Daily risk recompute) — 1.5 weeks |
| **Sprint 3** | #2 (Bias audit on publish, Fairlearn) — 2 weeks |
| **Sprint 4** | #7 (PMS scheduled reports) — 1 week; #6 (Tech file auto-population) — 2 weeks |
| **Sprint 5** | #3 (Drift via SDK inference logging) — 2 weeks |

By end of sprint 5 (~3 months), every Tier 2 page goes from "fill out a form" to "data appears automatically" — same UI, exponentially more useful.

---

## Strategic Note

The **biggest leverage** for "looks like a real product" is **Sprint 1** (HITL + Transparency). Both ship in <1 week each and turn two empty pages into pages that auto-populate during normal use. They alone make the demo dramatically more compelling without any external integration.

The **biggest leverage** for **production deployment** is **Sprint 5** (Drift via SDK). It's the feature that makes Sentinel a real ML observability tool, not just a compliance binder. Customers with deployed models will pay for it; compliance teams will pay for everything else but the deal is gated on Drift working.
