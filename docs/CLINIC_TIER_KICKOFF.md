# Clinic Tier — Kickoff (one-pager)

> **Audience:** founders + executing engineer(s). Companion to [`CLINIC_TIER_BLUEPRINT.md`](./CLINIC_TIER_BLUEPRINT.md). Read this first; the blueprint is the deep dive.

---

## 1. Phase order with calendar weeks

Assumes one full-time engineer, no concurrent work, sequential A→B then C→{D ∥ E}. Halve the total with a second engineer running D and E in parallel.

| Phase | Calendar | Strongest constraint | Output |
|---|---|---|---|
| **A — Spec** | Week 1 | Founder availability for sign-off | `docs/CLINIC_TIER_SPEC.md` + PRICING.md §2.3 |
| **B — Architecture** | Week 2 | Reviewer-agent agreement | `docs/CLINIC_TIER_ARCH.md` |
| **C — Foundations** | Weeks 3–5 | Haiku terminology swap quality | tier flag, i18n layer, 4-tile dashboard, nav predicate |
| **D — Features** | Weeks 6–7 | Browser-extension Manifest V3 packaging | tool registry, wizard, policy templates, plain-English alerts, Shadow-AI Lite |
| **E — Monetization** | Weeks 6–7 (parallel to D) | WeasyPrint template fidelity | stub Stripe SKUs, monthly PDF, clinic settings, BAA click-through, beta flag |

**Earliest paid clinic_basic customer:** end of Week 7 (with two engineers) or Week 9 (with one).

---

## 2. Files each phase touches

Inverted index — what each phase will modify.

| Phase | Touches |
|---|---|
| A | `docs/CLINIC_TIER_SPEC.md` (new), `docs/PRICING.md` (append §2.3 only) |
| B | `docs/CLINIC_TIER_ARCH.md` (new) |
| C | `policy_engine/models/organization.py`, `alembic/versions/<new>.py`, `policy_engine/services/tier_filter.py` (new), `policy_engine/routes/{auth,organizations}.py`, `dashboard/src/i18n/**` (new tree), `dashboard/src/{config/navigation.ts, types/index.ts, contexts/AuthContext.tsx, App.tsx}`, `dashboard/src/components/layout/AppLayout.tsx`, `dashboard/src/pages/clinic/**` (new), and 13 existing dashboard pages for the mechanical i18n key swap |
| D | `policy_engine/routes/clinic/{tools,onboarding,shadow_ai}.py` (new), `policy_engine/services/clinic_{policy_templates,alert_translator,shadow_detector}.py` (new), `dashboard/src/pages/clinic/{RegisterTool,OnboardingWizard,PolicyLibrary}.tsx` (new), `clinic-extension/**` (new top-level subdir) |
| E | `policy_engine/routes/billing/clinic.py` (new), `policy_engine/routes/clinic/{reports,settings,baa}.py` (new), `policy_engine/services/clinic_pdf_report.py` (new), `policy_engine/templates/clinic_report.html` (new), `policy_engine/main.py` (scheduler registration), `alembic/versions/<billing_events>.py`, `dashboard/src/pages/clinic/{settings/**, BaaModal.tsx}` (new), `dashboard/src/pages/admin/ClinicBeta.tsx` (new) |

Phases D and E **never** modify the same file — clean parallel execution.

---

## 3. Agents / skills each phase should invoke

| Phase | Primary skill | Sub-agents |
|---|---|---|
| A | `gsd-spec-phase` (or write directly with Opus) | `architect` for review |
| B | `architect` agent (Opus) — produce ARCH.md | `code-reviewer` for adversarial gate |
| C | `tdd-guide` (write tests first) → `planner` for sub-step DAG → parallel `Explore` + Sonnet implementers; **Haiku swarm** for the mechanical i18n swap (one agent per page); `frontend-design` for the 4-tile dashboard | `code-reviewer`, `typescript-reviewer`, `python-reviewer`, `security-reviewer` |
| D | `tdd-guide` per feature; `mcp-server-patterns` is **not** applicable; `e2e-runner` for onboarding wizard journey | `code-reviewer`, `python-reviewer`, `security-reviewer` (extension code) |
| E | `tdd-guide` for billing webhook + PDF worker; `database-reviewer` for the `billing_events` migration; `frontend-design` for the settings pages | `security-reviewer` (signed URLs, Stripe webhook signature), `database-reviewer` |

Cross-phase: invoke `gsd-verify-work` at the end of every phase. The `verification-loop` skill enforces the cross-phase invariants in BLUEPRINT.md §9 before the phase boundary unlocks the next phase.

---

## 4. Model tier per phase

| Phase | Model | Rationale |
|---|---|---|
| A | **Opus 4.7** | Spec writing is the highest-leverage step — every cell is reused for years. Use the deepest reasoner. |
| B | **Opus 4.7** | Architecture choices (tier-flag location, i18n shape, billing-stub forward-compat) cost the most to reverse. Opus. |
| C — substrate | **Sonnet 4.6** | Standard implementation work; large surface area; Sonnet is the best coding model. |
| C — terminology swap | **Haiku 4.5** | Mechanical "find string → wrap in `useT`" pattern. Parallelizable per file. 3× cost saving. |
| D | **Sonnet 4.6** | Five distinct feature implementations; coding-heavy; Sonnet. |
| E | **Sonnet 4.6** | Billing surface needs care (idempotency, signed URLs); still Sonnet's wheelhouse. Escalate any Stripe webhook ambiguity to Opus on demand. |

The Haiku swarm in Phase C is the single biggest cost-saving lever in this plan — ~13 page swaps × ~$0.05 vs Sonnet's ~$0.40 per swap.

---

## 5. Non-goals (explicit, this entire build)

- No transactional email or SMS in v1 (deferred — confirmed decision #2).
- No real plan-gating middleware in code; the `tier` column is the entire enforcement surface for v1.
- No hospital-grade network detector for clinics (Lite extension only; #5).
- No backend behavior change for existing `enterprise` orgs — invariant, not a goal we hit later.
- No new canonical role enum values (clinic-friendly role labels are display-only).
- No multi-currency pricing — USD only at launch.
- No upgrade flow from clinic_multi_site → enterprise in v1; sales-led.
- No customer-configurable risk-score weights at clinic tiers.
- No on-prem deployment path for clinic SKUs — SaaS multi-tenant only.
- No public marketing site work in this build (lives in a different repo).

---

## 6. Unresolved questions for the founders (need answers before Phase A unlock)

1. **Sales surface for Standard+ executed BAA** — does the founder run the BAA template through legal once, or per-customer? (Affects throughput beyond ~5 customers.)
2. **Stripe Payment Link vs. Stripe Checkout for stub billing** — Payment Link is the lighter path (no code), Checkout is closer to BILLING_IMPLEMENTATION.md (less migration later). Recommendation: **Payment Link for v1**, switch to Checkout when real billing lands.
3. **PDF report scope** — does month-end include zero-content sections ("you had 0 alerts this month") or skip them? Recommendation: **include with explicit zero**, conveys "we are watching."
4. **Shadow-AI Lite extension distribution** — Chrome Web Store published listing or unlisted/internal install? Recommendation: **unlisted + per-clinic install link** during beta; public listing at $50 paying clinics.
5. **Beta program admission** — opt-in waitlist or invite-only by founder? Recommendation: **invite-only first 10**, opt-in waitlist after.

---

## 7. Phase order (read-back per blueprint requirement)

> A — Spec → B — Architecture → C — Foundations (sub-step DAG, Haiku swarm) → {D — Features ∥ E — Monetization & launch}.

Critical path is A → B → C → max(D, E). With one engineer: ~8 weeks. With two engineers running D and E in parallel: ~5 weeks.

---

## Changelog

- **v0.1 — 2026-05-10** — initial kickoff doc generated by `blueprint` skill alongside `CLINIC_TIER_BLUEPRINT.md`. Awaiting founder review.
