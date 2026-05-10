# Sentinel AI — Pricing Plan

> **Status:** proposed v1. To be ratified by founders before customer-facing rollout. Audience: founders, sales, customer success, finance.

This document defines the SaaS pricing model for Sentinel AI. The companion docs are [`BILLING_IMPLEMENTATION.md`](./BILLING_IMPLEMENTATION.md) (engineering plan to ship it) and [`PLG_VS_ENTERPRISE.md`](./PLG_VS_ENTERPRISE.md) (the open-core alternative we considered and parked).

---

## 1. Pricing principles

Five rules drove every choice on this page.

1. **The SDK is free, forever.** It is the metering mechanism, not a product. Charging for it caps adoption among ML teams (the people who decide whether to instrument). Free SDK = data flows in = lock-in.
2. **Charge for what we govern, not what we transmit.** Per-evaluation pricing punishes scaled customers and is impossible to budget against. Per-model pricing aligns with how regulators and CMIOs actually think.
3. **Predictable monthly, not usage-based.** Healthcare procurement cannot approve a Datadog-shaped bill.
4. **The dashboard is the product.** All recurring revenue derives from it. The SDK is the trojan horse.
5. **Tier on capability, not on quotas.** Customers should hit a feature wall (e.g., they need Regulatory) before a quota wall — that is what makes them upgrade.

---

## 2. The plans

### 2.1 Standard tiers

| | **Starter** | **Professional** | **Enterprise** |
|---|---|---|---|
| **Monthly (annual prepay)** | $2,500 | $9,000 | Custom — typically $5K–$40K/mo |
| **Monthly (month-to-month)** | $3,000 | $11,000 | n/a (annual only) |
| **Annual prepay discount** | ~17% (2 months free) | ~18% | Negotiated |
| **Models under management** | 10 | 50 | Unlimited |
| **Seats** | 5 | 25 | Unlimited |
| **Audit log retention** | 1 year | 3 years | 6+ years (HIPAA-compliant) |
| **Support** | Email, 48h response | Email + Slack, 8h response | 24/7 dedicated CSM, 1h SLA |
| **Deployment** | SaaS (multi-tenant) | SaaS | SaaS, single-tenant, or on-prem |
| **HIPAA BAA** | Add-on | Included | Included |
| **SSO / SAML** | — | Google + Microsoft OAuth | + Okta, Azure AD, custom SAML |
| **Walkthrough modules** | Core, Clinical Governance, Risk | + Admin Governance, Financial, Regulatory | All modules |
| **Best for** | Single department, pilot | Mid-size hospital, ~50 active models | IDN, multi-site health system |

### 2.2 What "Modules included" means

Plan-tier feature flags hide entire dashboard sections. For example, a Starter customer literally does not see **Regulatory** in the left rail; they see the modules they pay for.

| Section | Starter | Pro | Enterprise |
|---|---|---|---|
| Core (Dashboard, Agents, Policies, Audit Logs, Alerts, Users) | ✓ | ✓ | ✓ |
| Clinical Governance (Model Cards, Bias, Drift, HITL) | ✓ | ✓ | ✓ |
| Risk (Portfolio, Score Detail) | ✓ | ✓ | ✓ |
| Admin Governance (Shadow AI, Scribe Audits, Transparency) | — | ✓ | ✓ |
| Financial (Prior Auth, Revenue Cycle) | — | ✓ | ✓ |
| Regulatory (Technical Files, Adverse Events, PMS) | — | ✓ | ✓ |
| Settings (Org, Risk Config, HIPAA Config) | ✓ (limited) | ✓ | ✓ |

Settings is "limited" in Starter because some controls (e.g., custom risk-score weights) are gated to Pro+.

---

## 3. One-time fees

These should be **genuinely one-time**, not recurring. Sold per engagement.

| Item | Price | What it covers |
|---|---|---|
| **Implementation — Starter** | $5,000 | Onboarding call, MLflow connector, 1 SSO setup, sample policies, demo data import. ~5 engineering days. |
| **Implementation — Professional** | $15,000 | Above + FHIR/DICOM hookup, custom policy authoring, 2 SSO connections, training session for up to 25 users. ~15 days. |
| **Implementation — Enterprise** | $25,000+ | Custom — typically white-glove deployment, on-prem packaging, SAML/SCIM, custom integrations, executive briefing. |
| **HIPAA BAA execution** | $2,000 | Legal review, document execution, partner due diligence. Free with Pro and Enterprise. |
| **On-prem deployment package** | $15,000 + 20%/yr maintenance | Hardened container images, Helm chart, air-gapped install runbook, DR runbook. |
| **Compliance officer training** | $3,500 / cohort (up to 10 attendees) | 4-hour live workshop on the Regulatory and Risk modules. |

---

## 4. Recurring add-ons (overage and upsells)

Where customers can spend more without renegotiating their tier.

| Add-on | Price | Notes |
|---|---|---|
| **Extra models above tier cap** | $150 / model / month | Soft cap at 110% triggers warning email; hard cap at 120% blocks new model-card publish. |
| **Extra seats above tier cap** | $50 / seat / month | Soft and hard caps mirror models. |
| **Extended audit retention** | $500 / month | Bump to 6 years for Starter or Pro (Enterprise includes). HIPAA wants 6yr; many state laws want more. |
| **24/7 priority support, 1h SLA** | $2,000 / month | Dedicated Slack channel, on-call escalation. Default for Enterprise. |
| **Designated CSM** | $1,500 / month | Quarterly business review, named contact. Default for Enterprise. |
| **Custom report templates** | $500 / template / month | Beyond the bundled PSUR / Technical File templates. |
| **Sandbox environment** | $1,000 / month | Isolated tenant for staging policy changes before prod. |

---

## 5. Discounts

| Lever | Discount |
|---|---|
| Annual prepay (Starter, Pro) | ~17% (the headline "2 months free") |
| Multi-year prepay | +5% / year (max 25%) |
| Non-profit health systems | 15% off list |
| Academic medical centers (research only) | 25% off list — separate research SKU |
| Design partners (first 10 customers) | 50% off Year 1, list price thereafter |
| Reference customer (case study + 1 reference call/qtr) | 10% off, ongoing |

Discount stacking caps at **40% off list** (40% off list ≈ contribution-margin floor based on current cost-to-serve).

---

## 6. Worked examples

### 6.1 Community hospital — pilot

- 1 ML model in pilot (sepsis prediction), 3 seats, no Regulatory needs yet.
- **Plan:** Starter, annual prepay → **$30,000/yr**.
- + Implementation: $5,000 one-time.
- **Year 1 total: $35,000.**

### 6.2 Mid-size hospital — production

- 35 active models, 18 seats, needs Regulatory for 2 FDA-cleared devices.
- **Plan:** Professional, annual prepay → **$108,000/yr**.
- + Implementation: $15,000 one-time.
- + 6-year retention: $6,000/yr.
- **Year 1 total: $129,000.** Year 2+: $114,000.

### 6.3 IDN — full deployment

- 5 hospitals, 220 models, 80 seats, on-prem required, 24/7 support.
- **Plan:** Enterprise, custom → **$240,000/yr** (negotiated).
- + Implementation: $25,000.
- + On-prem package: $15,000 + $3,000/yr maintenance.
- + 24/7 priority support: included.
- **Year 1 total: $283,000.** Year 2+: $243,000.

---

## 7. Selling motion

| Tier | Motion | Decision-maker | Cycle |
|---|---|---|---|
| Starter | Self-serve checkout (Stripe) or inside-sales | Director of IT or CMIO directly | Days–weeks |
| Professional | Mid-market AE with SE support | CIO + Compliance + CMIO | 2–4 months |
| Enterprise | Field sales + custom SOW | C-suite + procurement + legal | 4–9 months |

We hold the Starter line: no negotiation, no custom MSAs, click-through ToS only. Otherwise we destroy the unit economics on the smallest customers.

---

## 8. Competitor benchmarks (Q4 2025–Q1 2026, public info + analyst reports)

| Vendor | Entry | Enterprise | Meter |
|---|---|---|---|
| Credo AI | $24K/yr | $100K+/yr | Per-model |
| Monitaur | Enterprise-only, ~$60K/yr starting | $250K+/yr | Per-model + per-seat |
| Holistic AI | $30K/yr | $150K+/yr | Per-model |
| Fairly AI | $20K/yr | $120K+/yr | Per-model |
| Aporia | $12K/yr | Custom | Per-prediction (PLG) |
| Arize AI | Free → $50K/yr | Custom | Per-event (PLG) |

We sit deliberately ~10% above Credo AI and Holistic AI on list. Healthcare specialization (FHIR, DICOM, MDR PSUR auto-draft, HITL queue) is the premium.

---

## 9. What we will NOT charge for (yet)

These are deliberate choices — we may revisit, but defaulting to "free" while we grow.

- **The SDK and all telemetry it sends.** Per §1.
- **API calls from the dashboard to itself.** No per-API-call meter.
- **Read-only viewers from the patient-facing Transparency Portal.** It's marketing, not a product surface.
- **The first 100 audit log rows per agent in trial.** Trial overhead.

---

## 10. Open questions for the founders

1. Do we want a free tier for individual developers (1 model, 1 seat, community support)? See `PLG_VS_ENTERPRISE.md` — leaning **no** for now, revisit at $5M ARR.
2. Should we offer a 30-day free trial of Starter, or only paid pilots? Recommendation: **paid pilot only**, $5K minimum, credited toward Year 1 if they convert.
3. Do we honor the design-partner discount past 10 customers if the deal is strategic? Recommendation: **yes, but quarterly review**.
4. When does month-to-month go away? Recommendation: keep on Starter to enable self-serve, **remove on Professional** to enforce annual contracts.

---

## Changelog

- **v1 — 2026-05-10** — initial draft.
