# Sentinel AI — Billing & Plan-Gating Implementation Plan

> **Audience:** engineering. Companion to [`PRICING.md`](./PRICING.md). This is the build plan that turns the pricing model into shipped code.

---

## 1. Goal

Ship a working SaaS billing surface in **6 weeks of one engineer** (or 3 weeks of two). Endpoints:

- New customers can self-serve into Starter via Stripe Checkout.
- Existing customers see only modules in their plan.
- We meter `models_under_management` and `seats` against the plan cap.
- Soft- and hard-cap enforcement is automatic.
- Cancellations and downgrades flow through Stripe webhooks into the `organizations` table.

Out of scope for v1: dunning UI, in-app upgrade flow (sales-led for Pro/Ent), invoicing for Enterprise (handled manually by finance).

---

## 2. What we already have (don't rebuild)

The codebase is more SaaS-ready than it looks. Confirmed by reading:

- `policy_engine/models/organization.py` — `Organization` table with a `settings` JSON column. Plan metadata fits there with no new table needed for v1.
- `policy_engine/middleware/tenant_context.py` — already pulls `org_id` off the JWT and into `request.state`. Plan-gating middleware will read from the same place.
- `policy_engine/routes/organizations.py` — CRUD already exists. We add billing endpoints next to it, not as a sibling.
- `dashboard/src/config/navigation.ts` — already filters sections by role. We extend the same shape with a `requiredPlan` predicate.
- `dashboard/src/contexts/AuthContext.tsx` — already exposes the user object. We add `plan` to the response payload from `/v1/auth/login` and `/v1/auth/validate`.

What's missing: anything Stripe, anything plan-aware, anything metered. That's what this plan builds.

---

## 3. Data model changes

### 3.1 Extend `Organization`

Plan metadata lives in the existing `settings` JSON column for v1 (avoids a migration churn). Promote to first-class columns at v2 once the schema is stable.

```python
# Conceptual shape stored in Organization.settings["billing"]:
{
  "plan": "starter",                    # "starter" | "professional" | "enterprise" | "trialing"
  "stripe_customer_id": "cus_xxx",
  "stripe_subscription_id": "sub_xxx",
  "subscription_status": "active",      # active | past_due | canceled | trialing | unpaid
  "current_period_end": "2026-06-10T00:00:00Z",
  "model_cap": 10,
  "seat_cap": 5,
  "audit_retention_days": 365,
  "extra_models_purchased": 0,          # for overage SKU
  "extra_seats_purchased": 0,
  "billing_email": "billing@hospital.com",
  "trial_ends_at": null
}
```

Helper module to read/write this safely:

```
policy_engine/billing/
├── __init__.py
├── plans.py              # PLANS table — single source of truth for caps and modules
├── stripe_client.py      # thin wrapper around stripe-python
├── webhook_handler.py    # /v1/billing/webhook handler
├── usage.py              # count_models_for_org(), count_seats_for_org()
└── enforcement.py        # require_plan(), check_caps()
```

### 3.2 New table: `billing_events`

Audit trail of every Stripe event we processed. Required for support and dispute resolution.

```sql
CREATE TABLE billing_events (
  id UUID PRIMARY KEY,
  org_id UUID REFERENCES organizations(id),
  stripe_event_id TEXT UNIQUE NOT NULL,   -- idempotency key
  event_type TEXT NOT NULL,                -- e.g., 'customer.subscription.updated'
  payload JSONB NOT NULL,                  -- full webhook body
  processed_at TIMESTAMPTZ DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'processed' -- 'processed' | 'failed' | 'skipped'
);

CREATE INDEX idx_billing_events_org ON billing_events (org_id, processed_at DESC);
```

Add via Alembic migration:

```bash
alembic revision -m "add_billing_events_table"
```

### 3.3 No changes to existing tables

`agents`, `policies`, `model_cards`, etc. all already have `org_id`. We meter by querying them.

---

## 4. The plans table (single source of truth)

```python
# policy_engine/billing/plans.py
from dataclasses import dataclass
from typing import Literal

PlanName = Literal["starter", "professional", "enterprise", "trialing"]

@dataclass(frozen=True)
class Plan:
    name: PlanName
    model_cap: int
    seat_cap: int
    audit_retention_days: int
    modules: frozenset[str]
    stripe_price_id_monthly: str | None
    stripe_price_id_annual: str | None

CORE_MODULES = frozenset({"core", "clinical", "risk"})
PRO_MODULES = CORE_MODULES | {"admin_governance", "financial", "regulatory"}
ALL_MODULES = PRO_MODULES | {"settings_advanced"}

PLANS: dict[PlanName, Plan] = {
    "starter": Plan(
        name="starter",
        model_cap=10,
        seat_cap=5,
        audit_retention_days=365,
        modules=CORE_MODULES,
        stripe_price_id_monthly="price_starter_monthly",
        stripe_price_id_annual="price_starter_annual",
    ),
    "professional": Plan(
        name="professional",
        model_cap=50,
        seat_cap=25,
        audit_retention_days=1095,
        modules=PRO_MODULES,
        stripe_price_id_monthly="price_pro_monthly",
        stripe_price_id_annual="price_pro_annual",
    ),
    "enterprise": Plan(
        name="enterprise",
        model_cap=10**9,                 # effectively unlimited
        seat_cap=10**9,
        audit_retention_days=2190,       # 6 years
        modules=ALL_MODULES,
        stripe_price_id_monthly=None,    # custom only
        stripe_price_id_annual=None,
    ),
    "trialing": Plan(
        name="trialing",
        model_cap=3,
        seat_cap=2,
        audit_retention_days=30,
        modules=CORE_MODULES,
        stripe_price_id_monthly=None,
        stripe_price_id_annual=None,
    ),
}
```

This is the **only** place plan limits are defined. Both backend gating and frontend module hiding read from here (the frontend gets it via `/v1/billing/plan`).

---

## 5. Backend changes

### 5.1 New routes

Mount under `/v1/billing` next to `/v1/organizations`:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/billing/plan` | Returns current org's plan + caps + usage. Read by dashboard on login. |
| `POST` | `/v1/billing/checkout` | Creates a Stripe Checkout session for self-serve Starter signup. Returns `{url}`. |
| `POST` | `/v1/billing/portal` | Creates a Stripe Customer Portal session (manage card, cancel). Returns `{url}`. |
| `POST` | `/v1/billing/webhook` | Stripe webhook receiver. **No JWT** — verifies Stripe signature instead. |
| `GET` | `/v1/billing/usage` | Live counters: models in use vs. cap, seats vs. cap, retention. |

Wire into `policy_engine/main.py`:

```python
from policy_engine.routes import billing  # new module
app.include_router(billing.router, prefix="/v1/billing", tags=["billing"])
```

### 5.2 Webhook handling

The four events that matter for v1:

| Stripe event | Action |
|---|---|
| `checkout.session.completed` | Create org if new, attach `stripe_customer_id`, set plan from line items, set `subscription_status=active`. |
| `customer.subscription.updated` | Update plan + status + `current_period_end`. Handles upgrades/downgrades and renewals. |
| `customer.subscription.deleted` | Set `subscription_status=canceled`. Org keeps read access until `current_period_end`, then locks. |
| `invoice.payment_failed` | Set `subscription_status=past_due`. Show banner on dashboard; revoke write access after 7 days unless cleared. |

Idempotency: every handler first checks `billing_events.stripe_event_id` and bails if already processed. Stripe will retry — this is fine.

### 5.3 Plan-gating middleware

A new `PlanGateMiddleware`, mounted **after** `TenantContextMiddleware` so `request.state.org_id` is set:

```python
# policy_engine/middleware/plan_gate.py
class PlanGateMiddleware(BaseHTTPMiddleware):
    """
    Rejects API calls that require modules not in the org's plan.

    Reads `request.state.org_id` set by TenantContextMiddleware,
    looks up the org's plan, and 403s if the route's prefix is
    in a module the org has not paid for.
    """
    PREFIX_TO_MODULE = {
        "/v1/admin": "admin_governance",
        "/v1/finance": "financial",
        "/v1/regulatory": "regulatory",
        # Core, Clinical, Risk are unprotected — every paying plan includes them.
    }
```

403 response shape:

```json
{
  "error": "plan_upgrade_required",
  "message": "The Regulatory module is not included in your Starter plan.",
  "current_plan": "starter",
  "required_plan": "professional",
  "upgrade_url": "/billing/upgrade"
}
```

### 5.4 Cap enforcement (decorators)

Caps are checked at *write* time only — read endpoints stay open so a customer who hit their cap can still see their data while they upgrade.

```python
# policy_engine/billing/enforcement.py
from functools import wraps

def require_capacity(resource: Literal["models", "seats"]):
    """
    Decorator for create endpoints. Raises 402 Payment Required when over hard cap.
    """
    def decorator(fn):
        @wraps(fn)
        async def wrapped(*args, **kwargs):
            org_id = kwargs.get("org_id") or get_org_id_from_context()
            usage = await count_resource(org_id, resource)
            cap = get_org_cap(org_id, resource)
            if usage >= int(cap * 1.20):       # 120% = hard cap
                raise HTTPException(402, {
                    "error": "cap_exceeded",
                    "resource": resource,
                    "current": usage,
                    "cap": cap,
                    "upgrade_url": "/billing/upgrade",
                })
            return await fn(*args, **kwargs)
        return wrapped
    return decorator
```

Apply at:

- `policy_engine/routes/clinical/model_cards.py` — `@require_capacity("models")` on the publish endpoint (not draft creation — drafts shouldn't count).
- `policy_engine/routes/users.py` — `@require_capacity("seats")` on user creation.

Soft cap (110%): warning banner via WebSocket (`plan_warning` topic). Email at 100%, 110%, and on hard-cap block.

### 5.5 What "models under management" means

The meter is **published model cards**, not drafts:

```python
# policy_engine/billing/usage.py
async def count_models_for_org(db: AsyncSession, org_id: str) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(ModelCard)
        .where(ModelCard.org_id == org_id)
        .where(ModelCard.lifecycle_stage == "published")
    )

async def count_seats_for_org(db: AsyncSession, org_id: str) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(OrganizationMember)
        .where(OrganizationMember.org_id == org_id)
        .where(OrganizationMember.joined_at.isnot(None))
    )
```

This aligns with how customers think about value — drafts are scratch work, published cards are governed assets.

---

## 6. Frontend changes

### 6.1 Surface the plan in the auth payload

Backend: extend `/v1/auth/login` and `/v1/auth/validate` response to include the plan summary. Today they return the user; we add `plan`:

```typescript
// dashboard/src/types/index.ts (additions)
export type PlanName = 'starter' | 'professional' | 'enterprise' | 'trialing';

export interface PlanInfo {
  name: PlanName;
  modules: string[];               // ['core', 'clinical', 'risk', ...]
  caps: {
    models: number;
    seats: number;
  };
  usage: {
    models: number;
    seats: number;
  };
  status: 'active' | 'trialing' | 'past_due' | 'canceled';
  currentPeriodEnd: string;
}

export interface AuthState {
  user: User | null;
  plan: PlanInfo | null;
}
```

`AuthContext` exposes `plan` next to `user`. Components read it via `useAuth()`.

### 6.2 Plan-aware navigation

`navigation.ts` currently filters by `allowedRoles`. Add `requiredModule`:

```typescript
// dashboard/src/config/navigation.ts (sketch)
export interface NavSection {
  section: string;
  items: NavItem[];
  allowedRoles?: UserRole[];
  requiredModule?: ModuleKey;     // e.g., 'regulatory' — section hidden if plan lacks it
}

// New: getNavForUser(user, plan) replaces getNavForRole(user.role)
```

`AppLayout.tsx` switches its call from `getNavForRole(user.role)` to `getNavForUser(user, plan)`. One-line change.

### 6.3 Upgrade prompts

A reusable `<UpgradeGate module="regulatory">` component for any direct-link entry into a gated module. Two surfaces:

- **Sidebar:** module is hidden. No prompt — clean look for the customer's tier.
- **Direct URL:** `/regulatory/technical-files` typed by a Starter user → upgrade landing page with the relevant module's value prop and a **Talk to sales** CTA.

For self-serve upgrades (Starter → Pro), the CTA links to a Stripe Checkout via `/v1/billing/checkout?to=professional`.

### 6.4 Usage banners

`<UsageBanner>` mounted in `AppLayout.tsx`. Three states:

| Trigger | Banner | Action |
|---|---|---|
| Usage ≥ 90% of cap | Yellow info | "You're using 9 of 10 models. Add more →" |
| Usage ≥ 100% of cap | Orange warning | "You've hit your model cap. New models will publish but cost $150/mo each." |
| Usage ≥ 120% (hard cap) | Red error | "Model publish blocked. Upgrade to Professional →" |
| Subscription `past_due` | Red persistent | "Payment failed — update payment method to avoid service interruption →" |

### 6.5 Settings → Billing

New page `/settings/billing` (admin/system_admin only):

- Current plan, next renewal date, payment method (last 4).
- **Manage subscription** → opens Stripe Customer Portal in a new tab.
- **Upgrade plan** → upgrade checkout.
- **Invoices** — list of last 12 invoices with PDF download (proxied from Stripe).
- **Usage** — same data as the `<UsageBanner>` but persistent.

---

## 7. Stripe configuration

Done in the Stripe dashboard, captured here so it survives onboarding.

### 7.1 Products and prices

| Product | Prices |
|---|---|
| Sentinel Starter | `price_starter_monthly` ($3,000/mo), `price_starter_annual` ($30,000/yr) |
| Sentinel Professional | `price_pro_monthly` ($11,000/mo), `price_pro_annual` ($108,000/yr) |
| Sentinel Enterprise | Custom pricing — invoiced manually, no Stripe price |
| Extra Model | `price_extra_model` ($150/model/mo) — metered |
| Extra Seat | `price_extra_seat` ($50/seat/mo) — metered |
| Extended Retention | `price_retention_6yr` ($500/mo) |
| Priority Support | `price_priority_support` ($2,000/mo) |

### 7.2 Tax

Stripe Tax enabled — auto-calculates US sales tax. Healthcare exemptions handled via tax-exempt customer flag for non-profit health systems.

### 7.3 Webhook endpoint

- URL: `https://api.sentinel.ai/v1/billing/webhook`
- Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`, `invoice.payment_succeeded`
- Signing secret stored in `STRIPE_WEBHOOK_SECRET` env var.

### 7.4 Customer Portal

Configured to allow:
- Update payment method ✓
- Cancel subscription ✓ (immediate cancel disabled — only at period end)
- Update billing email ✓
- View invoices ✓
- **Disabled:** plan switching (we want them to come through our upgrade flow so we can capture the conversion).

---

## 8. Environment / config

Add to `.env.example`:

```bash
# Stripe
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx          # used by frontend for Stripe.js
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_STARTER_MONTHLY=price_xxx
STRIPE_PRICE_STARTER_ANNUAL=price_xxx
STRIPE_PRICE_PRO_MONTHLY=price_xxx
STRIPE_PRICE_PRO_ANNUAL=price_xxx
STRIPE_PRICE_EXTRA_MODEL=price_xxx
STRIPE_PRICE_EXTRA_SEAT=price_xxx

# Billing behavior
BILLING_HARD_CAP_MULTIPLIER=1.20             # 120% blocks writes
BILLING_SOFT_CAP_MULTIPLIER=1.10             # 110% warning banner
BILLING_PAST_DUE_GRACE_DAYS=7                # before write-revoke
```

`.env` (real, never committed) gets the live values when we go to prod.

---

## 9. Testing

Three layers, all required before launch.

### 9.1 Unit (pytest)

- `tests/billing/test_plans.py` — caps, module sets, serialization round-trip.
- `tests/billing/test_enforcement.py` — `require_capacity` decorator with mocked usage.
- `tests/billing/test_webhook_handler.py` — every Stripe event type with fixtures from Stripe CLI's `stripe trigger`.

### 9.2 Integration (pytest + Stripe test mode)

- Full lifecycle: checkout → webhook → org updated → access granted → cancel → grace period → access revoked.
- Run against Stripe test mode keys in CI; never against live Stripe.

### 9.3 E2E (Playwright)

- Self-serve checkout from landing page → land in dashboard with Starter plan visible.
- Hit model cap as Starter, see banner, click upgrade, complete pay, confirm Pro modules unlock.
- Past-due flow: simulate `invoice.payment_failed`, confirm banner, confirm read access remains, confirm write blocks after grace period.

Quarantine the live-Stripe webhook test if it becomes flaky — replace with replayed fixtures.

---

## 10. Rollout plan

### Phase 0 — Foundations (Week 1)

- Create Stripe account, configure products and webhook in test mode.
- Add `policy_engine/billing/` skeleton, `PLANS` table, migration for `billing_events`.
- Set every existing org to plan `enterprise` (free, manually billed) so nothing breaks.

### Phase 1 — Backend gating (Weeks 2–3)

- Implement `PlanGateMiddleware` and `require_capacity` decorator.
- Wire `/v1/billing/plan` and `/v1/billing/usage`.
- Internal QA: flip a test org to Starter and verify behavior.

### Phase 2 — Webhook + checkout (Week 4)

- `/v1/billing/webhook` with all four event handlers.
- `/v1/billing/checkout` + `/v1/billing/portal`.
- Stripe CLI replay testing.

### Phase 3 — Frontend (Week 5)

- Plan in `AuthContext`, plan-aware navigation, upgrade gate, usage banner, `/settings/billing` page.
- Mobile QA — banners and gates need to work in the responsive drawer.

### Phase 4 — Beta and launch (Week 6)

- Two friendly design partners on Starter for one billing cycle.
- Watch webhook event log for any unhandled types or idempotency violations.
- Public launch when zero unhandled events for 14 consecutive days.

---

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Stripe webhook missed → org plan drifts from reality | Idempotent handlers + nightly reconciliation job that pulls all subs from Stripe and diffs against `Organization.settings.billing.plan`. |
| Customer cancels mid-period → unfair lockout | Grace period: read access stays until `current_period_end`, then full lockout. |
| Customer disputes overage | Every overage decision logged with cap, count, and timestamp in `billing_events`. Support can replay the timeline. |
| Self-serve abuse (someone signs up 50 orgs to dodge caps) | Tie billing to a verified domain; one paid org per email domain unless sales manually grants. |
| Plan downgrade leaves customer over cap | Allow downgrade only via support ticket if usage > new plan's cap. Offer to delete excess models or auto-add overage. |
| Past-due notification missed | Send email at 1, 3, 7 days. Banner is sticky in app. CSM (for Pro/Ent) gets paged at day 3. |
| GDPR / HIPAA: Stripe holds PII | Customer email, address, last-4 only. No PHI ever leaves the Policy Engine. Document in BAA. |

---

## 12. What we explicitly defer

- **Per-evaluation usage billing** — out forever per the pricing principles.
- **In-app plan switching from Pro → Enterprise** — sales-led only.
- **Multi-currency** — USD only at launch; revisit when first non-US customer signs.
- **Dunning emails** beyond Stripe's defaults — revisit at 25 paying customers.
- **Procurement integrations (NetSuite, Workday)** — manual invoicing for Enterprise; automate if/when finance escalates.

---

## 13. Acceptance criteria for "shipped"

A v1 ship is true when **all** of these are true:

- [ ] A new customer can complete Stripe Checkout for Starter and land in a working dashboard with the Starter modules visible — without a single human action from us.
- [ ] A Pro customer who attempts to use a Regulatory route gets a clean 403 with `plan_upgrade_required`, not a generic error.
- [ ] A customer who hits the model cap sees a banner, can publish up to 120% of cap, and is hard-blocked at 121%.
- [ ] Webhook idempotency is provable: replaying any Stripe event twice produces the same final state.
- [ ] `Organization.settings.billing.plan` matches Stripe for every active org, and a nightly reconciliation job confirms it.
- [ ] Cancelled customers retain read access until `current_period_end`, then lose dashboard access entirely (audit logs preserved per retention policy).
- [ ] All four price IDs exist in production Stripe, all four matching env vars set in production policy engine.

---

## 14. Estimated cost

- **Engineering:** 6 person-weeks (~$30K loaded).
- **Stripe fees ongoing:** 2.9% + $0.30 per transaction. On $30K/yr Starter annual prepay → $900 fees per signup. Build into pricing margin.
- **Stripe Tax:** 0.5% of revenue.

Total cost-to-build is comfortably under one Year 1 Starter contract. Payback is on the first paying customer.
