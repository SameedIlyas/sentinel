# Sentinel AI — PLG vs Enterprise Sales: Which Motion First?

> **Audience:** founders making the go-to-market call. Decision deadline before we sign the first paying customer.

The pricing in [`PRICING.md`](./PRICING.md) is one of two viable routes. This doc lays out the alternative — a product-led growth (PLG) / open-core motion — side-by-side with the recommended top-down enterprise motion, and ends with a recommendation and a trigger for revisiting.

---

## 1. The two motions in one paragraph each

### Enterprise-first (what `PRICING.md` describes)

The dashboard is paid from day one. Self-serve only on the smallest tier. We sell to the CIO, CMIO, or compliance officer, with a 4–9 month cycle for Pro/Enterprise. Average contract value (ACV) is high ($30K–$250K+/yr). Customer acquisition cost (CAC) is high too — field sales, SE, security review, BAA, custom SOWs. Adoption inside the customer is top-down: governance and IT impose Sentinel on ML teams.

### Open-core / PLG (Aporia, Arize, Datadog model)

Free SDK and free dashboard up to a generous quota (e.g., 1M policy evaluations/month, 3 model cards, 5 seats). All Clinical Governance, Admin Governance, Financial, and Regulatory modules behind a paywall. ML and platform engineers drop the SDK in for free, hit limits or want gated modules, push internally for the paid plan. ACV is lower per customer but cycles are days-to-weeks. CAC is mostly content + docs + DevRel.

---

## 2. Side-by-side comparison

| Dimension | Enterprise-first | PLG / Open-core |
|---|---|---|
| **Free entry point** | None — paid pilot ($5K) is cheapest | Free tier (SDK + 3 model cards + 5 seats + Audit Logs) |
| **First customer ACV** | $30K–$108K | $0 → $12K–$30K after upgrade |
| **Time to first revenue** | 3–6 months | 0–2 months for upgrades |
| **Decision-maker** | CIO, CMIO, compliance officer | ML lead, platform engineer |
| **Champion needed inside customer** | Executive sponsor | Individual contributor |
| **Sales motion** | Field sales + SE + custom SOW | Self-serve + PLG ops + light inside sales |
| **CAC payback** | 12–18 months | 4–9 months |
| **Net revenue retention target** | 110–125% (expansion via models, modules) | 130%+ (expansion is the model — start small, grow inside) |
| **Compliance burden up-front** | High — BAA, SAML, SOC 2 expected on day 1 | Lower for free tier; high for upgrade |
| **Marketing primary surface** | Analyst reports (Gartner, Forrester), conferences (HIMSS), referrals | Docs, blog, GitHub presence, ML Slack communities |
| **Engineering load to launch** | 6 person-weeks (per `BILLING_IMPLEMENTATION.md`) | 10–14 person-weeks (free tier needs rate limits, anti-abuse, public docs site, sample apps) |
| **Risk of cannibalization** | Low | Real — free tier may satisfy customers who would have paid Starter |
| **Healthcare market fit** | High — hospitals expect this motion | Medium — clinicians don't self-serve; only ML teams do |
| **Data lock-in compounds via** | Long contracts, custom integrations | Telemetry volume, audit history depth |
| **Path to $10M ARR** | ~50 Pro customers + 20 Enterprise | ~500 paid customers + a few enterprise |
| **Best-in-class comparable** | Credo AI, Monitaur, Holistic AI | Aporia, Arize, Fiddler |

---

## 3. The "we'd be wrong if…" stress test

A useful exercise: what would have to be true for each motion to be the right call?

### Enterprise-first is right if…

- Hospitals and IDNs continue to centralize AI governance under the CIO/compliance office (they are — see Joint Commission AI standards 2026).
- The HIPAA, MDR, and EU AI Act compliance pressures keep growing (they are).
- Buyers value vendor-managed BAAs, SOC 2, and references over self-serve speed.
- Healthcare ML teams are *not* the buyers — they are the implementers (mostly true today).
- Our team can sell — we have or can hire someone who has closed $100K healthcare deals before.

### PLG is right if…

- Healthcare ML teams have real budget authority (rare; growing slowly at academic medical centers).
- We can produce content and DevRel at the rate Aporia and Arize do (~2 substantive blog posts/week + open-source examples + fast docs).
- We can survive 6 months of zero revenue while free tier scales.
- The free tier can be made cheap-to-serve (storage + bandwidth must scale linearly with revenue, not with usage).
- We are willing to compete on UX more than compliance — PLG users compare us to Datadog, not to a competing GRC vendor.

---

## 4. Hybrid options worth considering

These are not "pick one or the other" — there are three hybrid paths that solve real tensions.

### 4.1 Enterprise-first with a developer free tier (recommended hybrid)

Run the enterprise-first motion exactly as `PRICING.md` describes, but **add a free Developer tier**:

| | Developer (free) | Starter | Pro | Enterprise |
|---|---|---|---|---|
| Models | 3 | 10 | 50 | unlimited |
| Seats | 1 | 5 | 25 | unlimited |
| Audit retention | 7 days | 1 yr | 3 yr | 6 yr |
| Modules | Core only | Core + Clinical + Risk | + Admin/Financial/Regulatory | + Settings advanced |
| Support | Community | Email | + Slack | 24/7 |

Cost: ~3 extra weeks of engineering (rate limits, anti-abuse) on top of the enterprise build.

Why this works:
- ML engineers and indie healthcare developers can prototype with Sentinel for free.
- Brand recognition and inbound leads grow without inflating CAC.
- Small enough quotas that a real hospital cannot operate inside the free tier.
- Free tier acts as a *qualification funnel* — someone running 3 model cards in our sandbox is a better lead than a cold prospect.

### 4.2 Open-source the SDK, paid dashboard

The pricing already says SDK is free. Going one step further: **MIT-license the SDK** on GitHub. Customers can self-host the policy engine if they want; we charge for the managed dashboard and ongoing updates.

Pros:
- Maximum trust signal in healthcare (open-source = inspectable = securable).
- Free distribution via GitHub stars, conference talks, blog posts.
- Engineers will choose Sentinel on familiarity when they get to a buyer role.

Cons:
- Self-hosters never become customers — the value capture is purely the dashboard.
- Open source maintenance has fixed cost (issue triage, security patches, release management).

This is recommended **once we have 10 paying customers** — premature open-sourcing without a brand drains us.

### 4.3 Sell-through partners

Skip both PLG and direct enterprise. Sell through:
- **EHR vendors** (Epic App Orchard, Oracle Health) — they want governance for their AI offerings.
- **Cloud marketplaces** (AWS Healthcare, Azure Healthcare APIs) — co-sell.
- **Health systems' own innovation arms** that resell to peers.

Pros: zero CAC, distribution baked in.
Cons: 30–50% margin to the partner, no direct customer relationship, integration constraints.

This is a Year 2 motion, not a Year 1 motion.

---

## 5. Recommendation

**Run enterprise-first (per `PRICING.md`) for the first 12–18 months. Add the Developer free tier in month 6.**

Reasons:

1. Healthcare buyers expect the enterprise motion. Going PLG-first reads as "not serious" and disqualifies us from RFPs.
2. Our differentiation is healthcare specialization — FHIR cache, MDR PSUR auto-draft, HIPAA-aware shadow-AI scoring. These are not features ML engineers self-serve into; they are features compliance officers write into RFPs.
3. We have not yet built the content engine PLG demands. Without 2 substantive posts/week and a polished docs site, a free tier is just an unmonetized cost center.
4. Cash runway is finite. Three $30K Starter signups in Q1 is more concrete than 500 free signups and a hope.
5. The Developer tier (added month 6) captures the PLG benefit (brand, ML adoption) without the PLG cost (full free dashboard).

**Trigger to revisit:** if by month 9 we have <5 paying customers AND >200 inbound trial requests, we have a PLG market and an enterprise execution problem — flip the motion.

---

## 6. What does NOT change either way

Whether we go enterprise-first, PLG, or hybrid, these decisions hold:

- The SDK is free. (Per pricing principle 1.)
- We charge per model + per seat with module gating, not per evaluation.
- The Policy Engine is one codebase; tier differences are configuration, not forks.
- Compliance investment (BAA, SOC 2, HIPAA controls) happens in Year 1 regardless — required even for PLG to land healthcare customers.

The motion question affects *how we reach customers*, not *what we ship*.

---

## 7. Open questions

1. Is the founding team's strength sales (favors enterprise-first) or product/content (favors PLG)? **Be honest.** A founder who hates cold-calling will starve on enterprise-first. A founder with no DevRel instincts will starve on PLG.
2. What does our seed-round investor expect to see at Series A? Most healthcare-focused funds expect ACV growth (enterprise); most ML-tools-focused funds expect logo growth (PLG). Match the motion to the next round's pitch.
3. Do we have access to design partners through warm intros? If yes, enterprise-first is much faster. If no, PLG inbound may be the only viable path.
4. What is our realistic content production capacity? If we cannot publish weekly, PLG is a fantasy.

---

## 8. Decision record

To be filled in by founders:

- **Decision:**
- **Date:**
- **Decided by:**
- **Trigger to revisit:**
- **Owner of revisit check-in:**

---

## Changelog

- **v1 — 2026-05-10** — initial side-by-side analysis and recommendation.
