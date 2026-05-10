# Clinic Tier — Construction Blueprint

> **Audience:** engineering. **Status:** v0.1 — pre-execution. Source of truth for phase order, dependencies, and exit criteria. Generated 2026-05-10 by the `blueprint` skill.
>
> Companion docs: [`CLINIC_TIER_KICKOFF.md`](./CLINIC_TIER_KICKOFF.md) (one-pager), [`PRICING.md`](./PRICING.md), [`BILLING_IMPLEMENTATION.md`](./BILLING_IMPLEMENTATION.md), [`PLATFORM_OVERVIEW.md`](./PLATFORM_OVERVIEW.md).

---

## 0. Goal in one paragraph

Ship a **Clinic** product persona on top of the existing Sentinel AI healthcare governance platform. Same backend code path. Same database schema with one additive column. A tier-aware terminology layer and four-tile dashboard make a single-clinic customer feel they are using a product built for them — not a hospital tool with the dial turned down. Three new self-serve SKUs ($199 / $349 / $699 per month) sit beneath the existing Starter / Professional / Enterprise plans. No existing customer's behavior changes.

---

## 1. Operating decisions (locked before blueprint)

| # | Decision | Locked value |
|---|---|---|
| 1 | Billing dependency | **Ahead of `BILLING_IMPLEMENTATION.md`.** Stub billing — `tier` column on `Organization`, manual Stripe Payment Links, lightweight webhook to flip the column. Real `PLANS`-based gating bolts on later. |
| 2 | Email / SMS provider | **Deferred.** No transactional email or SMS in v1. |
| 3 | PDF generator | **WeasyPrint.** Python worker, HTML→PDF. |
| 4 | PDF delivery v1 | **Dashboard "Download latest report" card.** Cron writes object to storage; user pulls. No notifications. |
| 5 | Shadow-AI detector for clinics | **Browser extension + DNS-only Lite.** New code path, distinct from the hospital network detector. |
| 6 | HIPAA BAA stance | Basic = **click-through BAA** (writes `Organization.hipaa_baa_signed`). Standard / Multi-site = **executed BAA bundled** at sale. |
| 7 | Source-of-truth brief | No `CLINIC_TIER_BRIEF.md`. The prompt + existing docs are the source. Step 2 conflict detection is therefore a self-consistency check against `PRICING.md`, `PLG_VS_ENTERPRISE.md`, and the codebase. |

---

## 2. Codebase reality reconciliation

Read before any phase. Failure to internalize these will cause Phase B/C drift.

| Asserted by prompt | Reality on `main` | Resolution |
|---|---|---|
| `policy_engine/billing/plans.py` exists; clinic tiers extend it | Directory does not exist. `BILLING_IMPLEMENTATION.md` is a plan. | Phase E ships *stub billing*: `tier` flag + manual Payment Links. When the real billing system lands, clinic SKUs migrate into its `PLANS` dict — designed for that migration. |
| `dashboard/src/i18n/` exists | Does not exist. Strings are inline. | Phase C builds the i18n provider from scratch *before* doing terminology swaps. |
| Tier flag on `Organization` | `Organization.org_type` (enum HOSPITAL/PAYER/MEDTECH) and `Organization.settings` JSON exist. `hipaa_baa_signed` and `hipaa_baa_date` exist. | Add new `tier` column via Alembic migration. Reuse existing BAA columns for the click-through path. Do not put `tier` inside `settings` — query-layer filtering is cleaner against an indexed column. |
| `dashboard/src/config/navigation.ts` supports plan/tier predicates | Has `allowedRoles` only. Filters via `getNavForRole(role)`. No `requiredTier` or `requiredModule` today. | Phase C extends `NavItem` and `NavSection` with `requiredTier?: TierKey` and replaces `getNavForRole` with `getNavForUserAndTier(user, tier)`. Backwards compatible — sections without `requiredTier` are visible to every tier. |
| Clinic tier slots into `PRICING.md` cleanly | `PRICING.md` Starter line is **$2,500/mo** as the SMB-hospital floor and is explicitly described as "no negotiation, no custom MSAs, click-through ToS only." Clinic tiers ($199–$699) are 10–25× below this. | Phase A appends a **§2.3 Clinic tiers** section. The existing Starter line stands — a single-clinic with multiple departments may still upgrade to Starter. Sales motion table in §7 stays as written. |
| Role mapping table | `OrganizationMember.role` is a free `String` column (default `"member"`); canonical role enum lives in `dashboard/src/types/UserRole`. | Display-name mapping (Clinic-friendly label → canonical `UserRole`) lives in the i18n dictionary, *not* in the database. Canonical role values are unchanged. |

---

## 3. Phase graph (DAG)

```
        ┌───────────────────────────────────────┐
        │ A — Spec                              │  Opus  · 1 wk
        │   docs/CLINIC_TIER_SPEC.md            │
        └────────────────────┬──────────────────┘
                             │
                             ▼
        ┌───────────────────────────────────────┐
        │ B — Architecture                      │  Opus  · 1 wk
        │   docs/CLINIC_TIER_ARCH.md            │
        └────────────────────┬──────────────────┘
                             │
                             ▼
        ┌───────────────────────────────────────┐
        │ C — Foundations                       │  Sonnet (+ Haiku for swap)
        │   tier flag · i18n layer · 4-tile     │       · 2–3 wks
        │   dashboard · role-map · nav gating   │
        └────────┬──────────────────────────────┘
                 │
       ┌─────────┴─────────────┐
       ▼                       ▼
┌─────────────────────┐ ┌─────────────────────────┐
│ D — Features        │ │ E — Monetization+Launch │  Sonnet · ~2 wks each
│  · AI tool registry │ │  · stub Stripe SKUs     │
│  · 3-step wizard    │ │  · WeasyPrint PDF + cron│
│  · policy templates │ │  · clinic settings page │
│  · plain-English    │ │  · BAA click-through    │
│    alerts           │ │  · beta program flag    │
│  · Shadow-AI Lite   │ │                         │
└─────────────────────┘ └─────────────────────────┘
       (D and E run in parallel after C)
```

**Critical path:** A → B → C → D ∪ E. Worst-case calendar: ~7–8 weeks for one engineer; ~4–5 with two engineers running D and E in parallel.

---

## 4. Phase A — Spec

### A.1 Goal

Produce `docs/CLINIC_TIER_SPEC.md` — a falsifiable contract for what "Clinic" means before any architectural choice is made. Enables Phase B to refer back to a single document instead of re-arguing terminology.

### A.2 Dependencies

None. This is the upstream artifact.

### A.3 Self-contained context brief (for a fresh agent)

> "We are adding a Clinic product persona to Sentinel AI — same backend, clinic-friendly UX layer, three new SKUs at $199/$349/$699/mo. Read `docs/PLATFORM_OVERVIEW.md`, `docs/PRICING.md`, `docs/PLG_VS_ENTERPRISE.md`, and `docs/CLINIC_TIER_BLUEPRINT.md` §0–§2. Do not propose any architecture or code yet. Produce only the spec document with the four sections below."

### A.4 Sub-steps (serial — single-author doc)

| # | Step | Output |
|---|---|---|
| A1 | **Terminology dictionary** — every canonical platform noun (`model_card`, `bias_audit`, `hitl_queue`, `shadow_ai`, `agent`, `policy`, `audit_log`) mapped to its clinic-friendly display label per tier. | Section: "Terminology dictionary" |
| A2 | **Role mapping table** — clinic-friendly role names (e.g., "Practice Owner", "Office Manager", "Lead Clinician") mapped 1:1 to canonical `UserRole` values (`admin`, `compliance_officer`, `cmio`, `clinical_user`). | Section: "Role mapping" |
| A3 | **Tier-feature matrix** — Basic / Standard / Multi-site × {modules visible, model cap, seat cap, audit retention, BAA, support} | Section: "Tier matrix" |
| A4 | **BAA stance** — exact wording for click-through (Basic) and bundled (Standard+) BAA. References to `Organization.hipaa_baa_signed`. | Section: "Compliance posture" |
| A5 | **PRICING.md addendum** — append §2.3 "Clinic tiers" — table with the three SKUs, sits below §2.2 in the existing doc. | Edit: `docs/PRICING.md` |

### A.5 Files touched

- `docs/CLINIC_TIER_SPEC.md` (new)
- `docs/PRICING.md` (append section 2.3 only — no edits to 2.1 or 2.2)

### A.6 Exit criteria

- [ ] Tier matrix is testable as a JSON fixture (every cell has a deterministic value).
- [ ] Every canonical noun in `dashboard/src/types/index.ts` and `policy_engine/models/*` has a clinic-friendly display label per tier (or is explicitly marked "do not relabel").
- [ ] Role mapping is bijective — no clinic role label maps to two canonical roles, no canonical role is unreachable.
- [ ] PRICING.md still parses as one consistent document; existing §2.1 unchanged.
- [ ] One paragraph "what we are not building" surfaces the deferred email/SMS, deferred network detector, click-through BAA at $199.

### A.7 Adversarial gate (review before unlock of Phase B)

Reviewer (Opus sub-agent) confirms:

1. No constraint from §1 of this blueprint is silently relaxed.
2. The tier matrix can be encoded as `dict[Literal["clinic_basic", "clinic_standard", "clinic_multi_site"], TierConfig]` — same shape we will later port into `PLANS`.
3. Role mapping does not require any new canonical role enum value (additive only on the display side).
4. PRICING.md addendum does not contradict the existing "Starter line we hold" rule in §7.

---

## 5. Phase B — Architecture

### B.1 Goal

Produce `docs/CLINIC_TIER_ARCH.md` — the wiring diagram. Every interface that Phase C/D/E will implement is named here, with file paths and signatures, so each later phase can be executed by a fresh agent without re-deciding shape.

### B.2 Dependencies

A complete.

### B.3 Self-contained context brief

> "Read `docs/CLINIC_TIER_BLUEPRINT.md` (this file) and `docs/CLINIC_TIER_SPEC.md`. Read `policy_engine/models/organization.py`, `policy_engine/middleware/tenant_context.py`, `dashboard/src/config/navigation.ts`, `dashboard/src/contexts/AuthContext.tsx`, `dashboard/src/types/index.ts`. Produce `docs/CLINIC_TIER_ARCH.md` with the seven sections below. Reference real file paths and propose concrete signatures. Do not write production code yet."

### B.4 Sub-steps (serial — Opus, deep-reasoning)

| # | Decision documented |
|---|---|
| B1 | **Tier flag location** — new `tier` column on `Organization` (Alembic migration); enum `TierKey = enterprise \| clinic_basic \| clinic_standard \| clinic_multi_site`; default `enterprise` (every existing org). |
| B2 | **i18n layer pattern** — `dashboard/src/i18n/{provider.tsx, dict/en/{enterprise,clinic_basic,clinic_standard,clinic_multi_site}.ts, useT.ts}`. Tier resolved from `AuthContext.tier`. Key resolution: `useT('model_card.title')` → returns clinic-friendly label per tier, fallback to `enterprise`. |
| B3 | **Role mapping layer** — display-only. Lives in i18n dict (`dict/clinic_basic.ts → roles.admin = "Practice Owner"`). Canonical `UserRole` enum unchanged. |
| B4 | **Navigation tier predicate** — extend `NavItem`/`NavSection` with `requiredTier?: TierKey[]`; new `getNavForUserAndTier(user, tier)`; existing `getNavForRole` deprecated but kept until call sites migrate. |
| B5 | **PDF report worker placement** — `policy_engine/services/clinic_pdf_report.py`, scheduled by existing APScheduler in `policy_engine/main.py`. Output to `STORAGE_BACKEND` (S3 in prod, local FS in dev) at `clinic-reports/{org_id}/{yyyy-mm}.pdf`. Dashboard fetches via signed URL through `/v1/clinic/reports/latest`. |
| B6 | **Shadow-AI Lite architecture** — new `clinic-extension/` subdirectory (Manifest V3 browser extension) + new endpoint `/v1/clinic/shadow-ai/observations` that ingests DNS+page-context events. Feeds existing `Shadow AI` table but tagged `source="clinic_lite"` so the hospital detector path is undisturbed. |
| B7 | **Stub billing path** — `/v1/billing/clinic/payment-link` returns one of three pre-configured Stripe Payment Link URLs; minimal webhook at `/v1/billing/clinic/webhook` that on `checkout.session.completed` flips `Organization.tier` and writes a `billing_events`-shaped row (table created early — table is the same one BILLING_IMPLEMENTATION.md proposes). Designed so the full billing webhook handler in Phase 2 of `BILLING_IMPLEMENTATION.md` subsumes this without breaking schemas. |

### B.5 Files touched

- `docs/CLINIC_TIER_ARCH.md` (new)

### B.6 Exit criteria

- [ ] Every Phase C/D/E task in this blueprint has a referenced section in ARCH.md.
- [ ] The stub billing schema is forward-compatible with `BILLING_IMPLEMENTATION.md` §3–§5 (no column will need to change when real billing lands; behavior expands).
- [ ] The i18n provider design supports lazy-loading tier dictionaries (a clinic_basic user never downloads the enterprise dictionary).
- [ ] Navigation predicate change is additive — every existing role-only filter still works.

### B.7 Adversarial gate

Reviewer confirms (against constraints in §1):

1. **PHI never leaves Policy Engine** — PDF generation runs in `policy_engine/`; the dashboard receives a signed URL only. ✓ if true.
2. **Existing customers unchanged** — every existing `Organization` row migrates with `tier='enterprise'`; existing routes do not check `tier` unless newly tier-gated.
3. **No parallel billing system** — stub schema is a *subset* of BILLING_IMPLEMENTATION.md, not a competitor.
4. **Shadow-AI Lite is opt-in** — extension is per-clinic install; no impact on hospital detector path.

---

## 6. Phase C — Foundations

### C.1 Goal

Wire the substrate. After Phase C, a test org flipped to `clinic_basic` shows the new four-tile dashboard and clinic terminology; an existing `enterprise` org sees zero behavior change.

### C.2 Dependencies

B complete.

### C.3 Self-contained context brief

> "Read `docs/CLINIC_TIER_ARCH.md`. You are implementing the foundations: tier column, Alembic migration, i18n provider scaffolding, navigation predicate, role mapping dictionary, four-tile clinic dashboard. Do not implement clinic-specific *features* (those are Phase D) — only the substrate. Verify after each step that an `enterprise` user sees no behavior change."

### C.4 Sub-steps (parallelizable groups)

#### Group C-Backend (serial, Sonnet)

| # | Step | Files |
|---|---|---|
| C1.1 | Add `tier` column to `Organization` (Alembic migration) | `policy_engine/models/organization.py`, `alembic/versions/<new>.py` |
| C1.2 | Tier-aware filter helper `policy_engine/services/tier_filter.py` | new |
| C1.3 | Admin endpoint `POST /v1/organizations/{id}/tier` (system_admin only) to flip tier | `policy_engine/routes/organizations.py` |
| C1.4 | Surface `tier` in `/v1/auth/login` and `/v1/auth/validate` response | `policy_engine/routes/auth.py` |

#### Group C-Frontend-Substrate (serial, Sonnet)

| # | Step | Files |
|---|---|---|
| C2.1 | Create `dashboard/src/i18n/` — provider, `useT` hook, dictionary loader | new directory |
| C2.2 | Default English `enterprise.ts` dictionary that maps every current inline string to a key | new |
| C2.3 | Stub clinic dictionaries (`clinic_basic.ts`, `clinic_standard.ts`, `clinic_multi_site.ts`) — initially fall through to `enterprise` | new |
| C2.4 | Mount `<I18nProvider tier={authContext.tier}>` in `App.tsx` | `dashboard/src/App.tsx` |
| C2.5 | Extend `AuthContext` with `tier`; type `TierKey` in `types/index.ts` | `dashboard/src/contexts/AuthContext.tsx`, `dashboard/src/types/index.ts` |
| C2.6 | Extend `NavItem`/`NavSection` with `requiredTier?`; add `getNavForUserAndTier`; switch `AppLayout` call site | `dashboard/src/config/navigation.ts`, `dashboard/src/components/layout/AppLayout.tsx` |
| C2.7 | New `/clinic` route — four-tile dashboard, gated to clinic tiers only | `dashboard/src/pages/clinic/ClinicDashboard.tsx`, `App.tsx` |
| C2.8 | Role mapping in clinic dictionaries (e.g., `roles.admin = "Practice Owner"`) — no DB change | i18n dicts |

#### Group C-Mechanical-Swap (parallelizable per page, Haiku)

After C2.1–C2.6 land, Haiku does the bulk text-to-key replacement page-by-page. This is the cheapest model tier because the work is "find string → wrap in `useT(...)` → register key in `enterprise.ts`" with no design judgment.

Pages to swap, can run in parallel agents per file:

- `dashboard/src/pages/clinical/ModelCards.tsx`
- `dashboard/src/pages/clinical/BiasAudits.tsx`
- `dashboard/src/pages/clinical/DriftMonitor.tsx`
- `dashboard/src/pages/clinical/HitlQueue.tsx`
- `dashboard/src/pages/admin/ShadowAi.tsx`
- `dashboard/src/pages/admin/ScribeAudits.tsx`
- `dashboard/src/pages/finance/PriorAuthTrail.tsx`
- `dashboard/src/pages/finance/RevenueCycle.tsx`
- `dashboard/src/pages/regulatory/TechnicalFiles.tsx`
- `dashboard/src/pages/regulatory/AdverseEvents.tsx`
- `dashboard/src/pages/regulatory/PostMarket.tsx`
- `dashboard/src/pages/risk/RiskPortfolio.tsx`
- `dashboard/src/components/layout/*`
- `dashboard/src/components/common/*`

Each Haiku agent gets the same prompt with a different file. No two agents touch the same file → no merge conflict.

### C.5 Files touched (full list)

- `policy_engine/models/organization.py` — add `tier` column
- `alembic/versions/<new>.py` — migration
- `policy_engine/services/tier_filter.py` — new
- `policy_engine/routes/organizations.py`, `auth.py` — extend
- `dashboard/src/i18n/**` — entire new tree
- `dashboard/src/config/navigation.ts` — predicate
- `dashboard/src/types/index.ts` — `TierKey`, `PlanInfo` (forward-compat)
- `dashboard/src/contexts/AuthContext.tsx` — expose tier
- `dashboard/src/App.tsx` — i18n mount, `/clinic` route
- `dashboard/src/components/layout/AppLayout.tsx` — nav call site
- `dashboard/src/pages/clinic/**` — new
- 13 dashboard pages — terminology key swap (Haiku)

### C.6 Exit criteria

- [ ] `enterprise` org login renders identically to pre-change snapshot (visual diff test).
- [ ] `clinic_basic` org sees the `/clinic` route; the legacy hospital nav is hidden.
- [ ] Every dashboard string runs through `useT()` (lint rule enforced).
- [ ] `i18n` bundle for `clinic_basic` is < 50 KB gzipped (sanity check on lazy load).
- [ ] All existing Pro/Ent E2E tests pass unchanged.

### C.7 Adversarial gate

Reviewer (Opus) confirms:

1. No backend behavior change for `enterprise` orgs — every existing route path is unchanged unless explicitly tier-gated.
2. The Haiku terminology swap did not introduce semantic drift (sample 20 strings, verify display = original).
3. The i18n provider does not leak clinic dictionaries to enterprise users (network-tab check).
4. Migration is reversible (`alembic downgrade -1` works on a copy of prod).

---

## 7. Phase D — Clinic-specific features

### D.1 Goal

Ship the features that make the clinic UX distinct from a hospital UX with the dial turned down. After Phase D, a clinic_basic user can complete onboarding, register their AI tools, and see plain-English alerts — without ever encountering a model card or a bias audit table.

### D.2 Dependencies

C complete. (E does not depend on D — they run in parallel.)

### D.3 Self-contained context brief (per sub-step)

> "Read `docs/CLINIC_TIER_ARCH.md` §<sub-step ref> and `docs/CLINIC_TIER_SPEC.md` §<terminology dict, role mapping>. You are building <feature>. The tier flag is live. The i18n layer is live. The four-tile dashboard exists. Do not extend the enterprise feature surface — clinic features live in `policy_engine/routes/clinic/` and `dashboard/src/pages/clinic/`."

### D.4 Sub-steps (parallelizable)

| # | Step | Files (new unless noted) | Agent / model |
|---|---|---|---|
| D1 | **Manual AI tool registry form** — clinic-friendly version of model_card creation. Posts to `/v1/clinic/tools`, persists as a lightweight `ClinicalAiTool` row that maps to `model_card` with `lifecycle_stage='clinic_managed'`. | `policy_engine/routes/clinic/tools.py`, `policy_engine/models/clinical_ai_tool.py` (or extend ModelCard), `dashboard/src/pages/clinic/RegisterTool.tsx` | Sonnet |
| D2 | **3-step onboarding wizard** — first-login flow for a new clinic_basic org: (1) confirm BAA click-through, (2) register first AI tool, (3) enable Shadow-AI Lite extension. Stored in `Organization.settings.clinic_onboarding`. | `dashboard/src/pages/clinic/OnboardingWizard.tsx`, `policy_engine/routes/clinic/onboarding.py` | Sonnet |
| D3 | **Simplified policy templates** — preset library of 6–10 clinic-friendly policies ("Block PHI in public LLMs", "Require human review for clinical decision support", etc.). One-click apply creates real `Policy` rows. | `policy_engine/services/clinic_policy_templates.py`, `dashboard/src/pages/clinic/PolicyLibrary.tsx` | Sonnet |
| D4 | **Plain-English alert templates** — when an alert fires for a `clinic_*` tier, render it through a translation layer that swaps technical terms ("policy_evaluation rejected with constraint X") for clinic language ("Action blocked: tool tried to share patient information"). | `policy_engine/services/clinic_alert_translator.py`, integrated with existing alert pipeline | Sonnet |
| D5 | **Shadow-AI Lite — browser extension + DNS-only detector** — Manifest V3 extension installed per clinic, reports DNS lookups + page-context AI tool detections to `/v1/clinic/shadow-ai/observations`. Tagged `source='clinic_lite'`. | `clinic-extension/**` (new top-level subdir), `policy_engine/routes/clinic/shadow_ai.py`, `policy_engine/services/clinic_shadow_detector.py` | Sonnet |

D1–D4 can run in 4 parallel sub-agents (no shared files). D5 has its own subdirectory and runs alongside.

### D.5 Files touched

New directories: `policy_engine/routes/clinic/`, `policy_engine/services/clinic_*`, `dashboard/src/pages/clinic/`, `clinic-extension/`. No modification of any existing enterprise route handler.

### D.6 Exit criteria

- [ ] A new clinic_basic org can complete onboarding in < 15 minutes (clock-tested with one engineer + one founder as guinea pigs).
- [ ] At least one tool registered, one policy applied, one shadow-AI observation logged via the extension on a test browser.
- [ ] Plain-English alerts pass a "would a non-technical office manager understand this?" eyeball test on 10 sample alerts.
- [ ] Enterprise alert wording is unchanged for enterprise orgs.

### D.7 Adversarial gate

Reviewer confirms:

1. Every clinic-only file lives under `*/clinic/` or `clinic-*` — no accidental enterprise mutation.
2. The browser extension does not transmit PHI — only DNS host names and AI-tool fingerprints.
3. Template policies use the same `Policy` schema as enterprise; no parallel policy table.
4. The plain-English translator falls back to the technical alert text if no clinic translation exists (graceful degradation).

---

## 8. Phase E — Monetization & launch

### E.1 Goal

Ship the SKUs and the monthly compliance PDF that justifies the recurring fee. Beta-program flag lets us turn on / off real customers individually before public launch.

### E.2 Dependencies

C complete. Independent of D.

### E.3 Self-contained context brief

> "Read `docs/CLINIC_TIER_ARCH.md` §B7 (stub billing) and §B5 (PDF worker). The tier flag exists; the i18n layer exists. Three Stripe Payment Links have been created in the dashboard (URLs supplied via env vars). Build the smallest billing surface that lets a clinic pay $199/mo, the cron that produces a monthly PDF, the settings page, and the beta feature flag. Do not implement plan-gating in code — the tier flag is the entire enforcement surface for v1."

### E.4 Sub-steps (parallelizable)

| # | Step | Files | Agent / model |
|---|---|---|---|
| E1 | **Stub Stripe SKUs + minimal webhook** — three Payment Links via env (`STRIPE_PAYMENT_LINK_CLINIC_{BASIC,STANDARD,MULTI_SITE}`); endpoint that flips `Organization.tier` on `checkout.session.completed`; `billing_events` table created early so it is shape-compatible with `BILLING_IMPLEMENTATION.md`. | `policy_engine/routes/billing/clinic.py` (new), `alembic/versions/<billing_events>.py` | Sonnet |
| E2 | **WeasyPrint PDF report worker** — APScheduler job runs monthly; pulls per-org rollups (tools, policy hits, alerts, BAA status); renders HTML→PDF; writes to `STORAGE_BACKEND://clinic-reports/{org}/{yyyy-mm}.pdf`. | `policy_engine/services/clinic_pdf_report.py`, `policy_engine/templates/clinic_report.html`, `policy_engine/main.py` (scheduler registration) | Sonnet |
| E3 | **"Download latest report" dashboard card** — new card on `/clinic` calling `GET /v1/clinic/reports/latest` → signed URL. | `policy_engine/routes/clinic/reports.py`, `dashboard/src/pages/clinic/ClinicDashboard.tsx` | Sonnet |
| E4 | **Clinic settings pages** — three tabs: Practice info, Compliance (BAA click-through + audit retention indicator), Billing (current SKU + manage subscription link to Stripe Customer Portal). | `dashboard/src/pages/clinic/settings/{Practice,Compliance,Billing}.tsx`, `policy_engine/routes/clinic/settings.py` | Sonnet |
| E5 | **BAA click-through flow** — Basic-tier modal on first login; on accept, writes `Organization.hipaa_baa_signed = true`, `hipaa_baa_date = now()`, source `'click_through'` recorded in `settings.baa_source`. Standard+ shows BAA-on-file status only (executed BAA loaded by sales). | `dashboard/src/pages/clinic/BaaModal.tsx`, `policy_engine/routes/clinic/baa.py` | Sonnet |
| E6 | **Beta program flag** — `Organization.settings.clinic_beta = true \| false`; admin-only UI to toggle; gates whether the org sees clinic features at all (acts as a kill switch during beta). | `policy_engine/routes/admin/clinic_beta.py`, `dashboard/src/pages/admin/ClinicBeta.tsx` | Sonnet |

E1, E2, E4, E5, E6 are file-disjoint and run in parallel. E3 depends on E2 and runs after.

### E.5 Files touched

New: `policy_engine/routes/billing/clinic.py`, `policy_engine/routes/clinic/{reports,settings,baa}.py`, `policy_engine/services/clinic_pdf_report.py`, `policy_engine/templates/clinic_report.html`, `dashboard/src/pages/clinic/{settings/**, BaaModal.tsx}`. Edits: `policy_engine/main.py` (scheduler), `alembic/versions/`.

### E.6 Exit criteria

- [ ] A clinic_basic test org can pay via Stripe Payment Link → tier flips → onboarding wizard appears at next login.
- [ ] Monthly cron runs against test org and produces a downloadable PDF with non-empty sections for tools, policies, alerts, BAA status.
- [ ] Click-through BAA writes the timestamp; the resulting state is observably equal to a Standard+ executed BAA in the database.
- [ ] Beta flag set to `false` hides the `/clinic` route entirely (used as a kill switch).
- [ ] No enterprise org accidentally receives a clinic PDF.

### E.7 Adversarial gate

Reviewer confirms:

1. **No PHI in PDF or in storage.** The clinic report uses anonymized rollups only — counts, percentages, lifecycle stages. Verified by reading the template.
2. **Stub billing schema is a strict subset of `BILLING_IMPLEMENTATION.md`** — when the real billing system lands, no clinic table needs to migrate; only the webhook handler grows.
3. **Click-through BAA is legally adequate for $199/mo** — locked decision (#6 above). Document the legal opinion in the spec.
4. **Object storage signed URLs expire** ≤ 1 hour and are scoped per-org.

---

## 9. Cross-phase invariants (hold for every phase)

A reviewer agent runs this checklist after every PR in any phase. A red box blocks merge.

| Invariant | How to verify |
|---|---|
| No backend behavior change for existing `enterprise` orgs | Snapshot tests + manual verification on demo data |
| PHI never leaves the Policy Engine | Trace every new outbound payload (PDF, email, signed URL) — only metadata, no patient data |
| Tier flag is the only enforcement surface in v1 | grep for `org.tier ==` — should only appear in tier_filter, navigation, and `/clinic` route guards |
| `Organization.tier` always has a value | Migration default + non-null constraint |
| Existing tests pass on every phase boundary | `pytest`, `npm test`, Playwright suite |
| Stub billing schema is a strict subset of BILLING_IMPLEMENTATION.md | Schema diff at end of phase E |

---

## 10. Plan mutation protocol

Steps in this blueprint can be **split**, **inserted**, **skipped**, **reordered**, or **abandoned** under the following rules.

| Mutation | Rule |
|---|---|
| **Split** a step | Open a follow-up PR with `[blueprint-mutation: split D2]` in the title. Append rationale to this doc's Changelog. |
| **Insert** a step | Allowed only between phase boundaries (not mid-phase). Append the new step letter (e.g., `C.9`). |
| **Skip** a step | Requires founder sign-off recorded in this doc. Skipping is not the same as deferring — see the "Out of scope" list. |
| **Reorder** within a phase | Allowed if the sub-step DAG permits it. Update the "Sub-steps" tables here. |
| **Abandon** a phase | Triggers a rebuild of this blueprint. Do not partially abandon — either ship the phase or revert. |

All mutations leave an audit-trail entry in §12 Changelog.

---

## 11. Out of scope (this blueprint)

Surface here so they don't quietly creep in.

- Email / SMS notifications (deferred per decision #2).
- Real plan-gating in code path (deferred until `BILLING_IMPLEMENTATION.md` ships — clinic tier rides on the `tier` column alone).
- Hospital-grade network shadow-AI detector for clinics (decision #5: Lite only).
- Custom risk-score weights per clinic tier (clinic UI uses the platform default; no Settings → Risk page in clinic nav).
- Multi-clinic federation features (Multi-site is a single org with sub-locations; true federation = enterprise).
- In-app upgrade flow from clinic_multi_site → enterprise (sales-led; same as Pro → Enterprise today).
- Per-clinic pricing customization (locked at $199/$349/$699 — `gsd-style` discounts via PRICING.md §5 still apply).
- Patient-facing transparency portal customization (uses platform default).

---

## 12. Changelog

- **v0.1 — 2026-05-10** — initial blueprint generated by `blueprint` skill. Awaiting founder sign-off before Phase A unlock.
