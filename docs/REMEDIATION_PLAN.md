# Sentinel AI — CRITICAL Remediation Plan

> **Generated:** 2026-05-19
> **Branch state at plan time:** `feat/clinical-shield-v1` HEAD `011b15b`
> **What this is:** per-PR tickets for the 12 remaining CRITICAL findings,
> each one scoped to a single merge, with acceptance criteria, files
> touched, test plan, and explicit gotchas. Designed for one engineer to
> own one ticket end-to-end in a single working session (most) or one
> working week (the audit-chain redesign).
> **What this is not:** an implementation. The plan is the contract; the
> implementation lives in each PR.
> **Source of truth for findings:** `REVIEW.md` (full audit) and
> `READINESS_ASSESSMENT.md` (deployment-shape impact).

---

## Status tracker

| ID | Status | PR / commit |
|---|---|---|
| CRIT-007 — auth blacklist on `authenticate_request` | ✅ landed | `714256b` |
| CRIT-001 — tenancy on `/v1/audit/logs` | ✅ landed (audit-route slice only) | `011b15b` |
| CRIT-001 (rest) — tenancy on agents / policies / alerts | ✅ landed | `13e21e8` |
| CRIT-004 — tenancy on `/v1/clinical/hitl/*` | ✅ landed | `13e21e8` |
| CRIT-013 — WebSocket ticket pattern | ✅ landed | `10ec333` |
| CRIT-009 — Postgres `userrole` enum healthcare values | ✅ landed | `9c1af08` |
| CRIT-012 — tier guards on `/clinic/*` dashboard routes | ✅ landed | `7edcee0` |
| CRIT-011 — Zod-validate localStorage user object | ✅ landed (partial — HttpOnly cookie deferred) | `893daa6` |
| CRIT-006 — Stripe `subscription.updated` writes `org.tier` | ✅ landed | `a73dbe7` |
| CRIT-010 — `organization_id NOT NULL` × 13 tables | ✅ landed | `0719566` |
| CRIT-008 — retention with legal-hold + archive durability | ✅ landed | `2d4431b` |
| CRIT-005 — prior-auth seq_no + tail-deletion detection | ✅ landed | `5689a6e` |
| CRIT-002 + CRIT-003 — HITL audit-chain redesign | ✅ landed | `8ce2c4c` |
| W-1 — dev deps (stripe / freezegun / testcontainers) | ✅ landed | `10ec333` |

Order is **not** strictly required, but the dependency arrows below tell you
which PRs unblock which.

```
PR#5 (enum) ──┐
              │
PR#9 (NOT NULL) ──┐
                  │
PR#2 (agents/policies/alerts) ──► PR#3 (HITL) ──► PR#12 (HITL chain)
                  │                                  │
                  └──► PR#10 (retention)             │
                                                     │
PR#4 (WS ticket) ─┐                                  │
                  │                                  │
PR#11 (prior-auth seq_no) ───────────────────────────┘
                                                     
PR#6 (clinic tier guard)  — independent              
PR#7 (Zod user)           — independent              
PR#8 (Stripe tier)        — depends on stripe SDK dev dep
```

---

## PR #2 — Tenancy filters on `/v1/agents`, `/v1/policies`, `/v1/alerts`

**Closes:** CRIT-001 (remaining), plus the equivalent HIGH-rated tenancy gaps
on the same surfaces.

### Files touched

| File | Change |
|---|---|
| `policy_engine/routes/agents.py` | Swap `authenticate_request` → `authenticate_request_context` on list/get/update/delete; scope every query to `auth.organization_id`; SYSTEM_ADMIN bypass. |
| `policy_engine/routes/policies.py` | Same pattern. Also confirm POST writes `organization_id = auth.organization_id` (do **not** trust `payload.organization_id`). |
| `policy_engine/routes/alerts.py` | Same pattern. The mutation routes (acknowledge / resolve / dismiss) need the scope on the `db.query(Alert).filter(Alert.id == alert_id)` lookup, not just the list. |
| `tests/test_agents_tenancy_isolation.py` (new) | Cross-tenant 404 / hidden-from-list assertions. |
| `tests/test_policies_tenancy_isolation.py` (new) | Same. |
| `tests/test_alerts_tenancy_isolation.py` (new) | Same — including the mutation endpoints. |

### Acceptance criteria

- [ ] An ORG_ADMIN at org A calling `GET /v1/agents` does not see any agent
      whose `organization_id != A`.
- [ ] `GET /v1/agents/{id}` returns 404 for cross-tenant IDs (never 403 — 403
      leaks existence).
- [ ] `PATCH /v1/policies/{id}` and `DELETE /v1/policies/{id}` cross-tenant
      requests return 404.
- [ ] `POST /v1/alerts/{id}/acknowledge` cross-tenant returns 404.
- [ ] SYSTEM_ADMIN bypass works for every list/get; documented in the route
      docstring.
- [ ] Existing tests that don't set `organization_id` on fixtures still pass —
      seed an `organization_id` in `tests/factories/` defaults.
- [ ] New per-route tenancy tests pass.

### Gotchas

- The existing route signatures use `auth_id: str = Depends(authenticate_request)`.
  Change to `auth: AuthContext = Depends(authenticate_request_context)`. Any
  helper in the route body that referenced `auth_id` becomes `auth.identity`.
- `tests/factories/` likely creates rows without `organization_id`. Don't
  paper over with a default of `None` — assign a real org so the new tests
  exercise the filter rather than vacuously pass.
- `routes/alerts.py` has a "create alert" path called from the policy
  evaluation engine. Make sure the synthesised alert sets `organization_id`
  from the policy's owner org, not from `request.state`.

### Effort

3–5 engineer-days (bulk of the time is the fixture/test sweep, not the
route changes).

---

## PR #3 — Tenancy on `/v1/clinical/hitl/*`

**Closes:** CRIT-004.

### Files touched

| File | Change |
|---|---|
| `policy_engine/routes/clinical/hitl.py` | Scope every list/get/assign/approve/reject/escalate/audit-trail endpoint. The `_get_review_or_404` helper currently filters only by `id`; add `HITLReview.organization_id == auth.organization_id`. On POST, ignore `payload.organization_id` and force `auth.organization_id`. |
| `policy_engine/routes/clinical/hitl.py` | Audit-trail endpoint must also scope by the parent review's org, not the caller's. |
| `tests/clinical/test_hitl_tenancy_isolation.py` (new) | Regression: ORG_ADMIN at clinic A receives 404 on every clinic-B HITL endpoint. |

### Acceptance criteria

- [ ] `GET /v1/clinical/hitl/reviews` returns only the caller's org rows.
- [ ] `GET /v1/clinical/hitl/reviews/{id}` returns 404 cross-tenant.
- [ ] `POST /v1/clinical/hitl/reviews/{id}/approve` cross-tenant returns 404
      and writes no audit row.
- [ ] `POST /v1/clinical/hitl/reviews/{id}/reject` same.
- [ ] `POST /v1/clinical/hitl/reviews/{id}/escalate` same.
- [ ] `GET /v1/clinical/hitl/reviews/{id}/audit-trail` cross-tenant 404.

### Gotchas

- This PR must merge **before** PR #12 (audit-chain redesign) — the chain
  rewrite operates on tenant-scoped queries, so the scope contract has to
  be the same in both PRs.

### Effort

2–3 engineer-days.

---

## PR #4 — WebSocket ticket pattern (JWT out of URL)

**Closes:** CRIT-013.

### Files touched

| File | Change |
|---|---|
| `policy_engine/routes/websocket.py` | Replace `?token=<JWT>` handshake with `?ticket=<id>`. Server exchanges ticket → user → discards. |
| `policy_engine/routes/ws_ticket.py` (new) | `POST /v1/ws/ticket` returns `{ticket: str, expires_in: 30}`. Authenticated via JWT in `Authorization` header (so JWT never reaches a URL). |
| `policy_engine/services/ws_ticket_store.py` (new) | Redis-backed single-use store. `setex(ticket, 30, user_id)`, `getdel(ticket)` for atomic exchange. Fallback to an in-memory dict for tests. |
| `dashboard/src/hooks/useWebSocket.ts` | New `useWebSocket` flow: (1) POST to /v1/ws/ticket, (2) open WS with `?ticket=`. Existing reconnect / callback logic preserved (HIGH-027 fix). |
| `dashboard/src/hooks/__tests__/useWebSocket.ts` | New test asserts the ticket POST happens once per connect. |
| `tests/test_ws_ticket.py` (new) | Ticket is single-use; expires after 30 s; opaque (no PII). |

### Acceptance criteria

- [ ] No JWT ever appears in a WebSocket URL.
- [ ] Ticket store: TTL 30 s, single-use (getdel), opaque random.
- [ ] WS handshake fails with `4401` close code on missing/expired/used
      ticket.
- [ ] Dashboard reconnect path requests a fresh ticket each time.
- [ ] Old behaviour (JWT in URL) removed — no fallback. Bumps the WS API
      version header.

### Gotchas

- The dashboard's reconnect logic in `useWebSocket.ts` was just stabilised
  in HIGH-027 — don't reintroduce duplicate connections. Memoise the
  ticket fetch via the ref pattern already in place.
- Multi-replica deployments: ensure the ticket store is the real Redis,
  not an in-memory fallback, in production. Add a startup-guard that
  refuses to start with `APP_ENV=production` and an in-memory ticket
  store.

### Effort

3–4 engineer-days.

---

## PR #5 — PostgreSQL `userrole` enum healthcare values

**Closes:** CRIT-009.

### Files touched

| File | Change |
|---|---|
| `alembic/versions/2026_NN_NN_NNNN-019_userrole_healthcare_values.py` (new) | `op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'cmio';")` for each of: `cmio`, `data_scientist`, `compliance_officer`, `clinical_user`, `system_admin`. Wrap in `op.get_bind().exec_driver_sql` outside the transaction (`autocommit_block` in alembic). |
| `policy_engine/models/user.py` | Reconcile the `ADMIN`/`ORG_ADMIN` alias collision — both currently have value `"admin"`. Pick a primary and remove the alias. The enum on Postgres can have only one `"admin"` slot. |
| `tests/test_migration_019_role_enum.py` (new) | Round-trip migration test that asserts the enum contains all 8 values after upgrade. Postgres-only. |

### Acceptance criteria

- [ ] Migration applies cleanly on a fresh Postgres DB.
- [ ] Migration applies cleanly on top of an existing Postgres DB at head.
- [ ] SQLite skip-block preserved (enum is text on SQLite — no-op).
- [ ] After upgrade, `INSERT INTO users (..., role) VALUES (..., 'cmio')`
      succeeds on Postgres.
- [ ] `ADMIN`/`ORG_ADMIN` collision documented and resolved.

### Gotchas

- `ALTER TYPE ... ADD VALUE` is non-transactional in Postgres — must run
  outside the alembic transaction. Use:
  ```python
  with op.get_context().autocommit_block():
      op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'cmio';")
  ```
- The alias collision in `models/user.py` is load-bearing for `R2` (clinic
  product-role projection). The R2 change uses `'admin'` literal — leave
  that intact and just remove the *Python-side* alias without changing the
  enum value.

### Effort

1 engineer-day.

---

## PR #6 — Tier guards on `/clinic/*` dashboard routes

**Closes:** CRIT-012.

### Files touched

| File | Change |
|---|---|
| `dashboard/src/components/auth/ProtectedRoute.tsx` | Accept `requiredTiers?: TierKey[]`. If set, return `<AccessDenied/>` for users whose `tier` not in the list. |
| `dashboard/src/App.tsx` | Wrap all 11 `/clinic/*` routes with `requiredTiers={CLINIC_ALL_TIERS}`. |
| `dashboard/src/types/index.ts` | Export `CLINIC_ALL_TIERS` constant (`['clinic_basic', 'clinic_standard', 'clinic_multi_site']`). |
| `dashboard/src/components/auth/__tests__/ProtectedRoute.tsx` | Render with `requiredTiers={['clinic_basic']}`, user tier `'enterprise'` → AccessDenied; user tier `'clinic_basic'` → child renders. |
| **Server-side enforcement:** every `/v1/clinic/*` route in `policy_engine/routes/clinic/` | Add a `require_clinic_tier` dependency that 403s if the user's org tier is not clinic-family. |

### Acceptance criteria

- [ ] Typing `/clinic/settings/compliance` as an enterprise-tier user
      renders AccessDenied, not the BAA form.
- [ ] All 11 `/clinic/*` routes pass the same gate.
- [ ] Server-side enforcement on the matching `/v1/clinic/*` API routes
      means client-side bypass still 403s.
- [ ] Vitest unit tests for `ProtectedRoute` pass.
- [ ] No existing clinic-tier walk-through breaks.

### Gotchas

- Server-side tier enforcement is the **authoritative** check. Client-side
  is for UX only. Add tests on both surfaces or the gate is cosmetic.
- The sidebar already filters by tier — but the routing layer does not.
  This PR is about the routing layer, not the sidebar.

### Effort

1–2 engineer-days.

---

## PR #7 — Zod-validate `localStorage` user object

**Closes:** CRIT-011 (partial — the localStorage XSS surface still exists;
moving JWT to HttpOnly cookies is a follow-up).

### Files touched

| File | Change |
|---|---|
| `dashboard/package.json` | Add `zod` (current latest minor). |
| `dashboard/src/types/userSchema.ts` (new) | `UserSchema = z.object({ id, username, email, role: z.enum([...]), tier: TierKeySchema.optional(), … })`. |
| `dashboard/src/api/client.ts` (around `getUser`) | Wrap `JSON.parse(userStr)` in `UserSchema.safeParse()`. On failure, clearUser and return `null`. Never return an object that hasn't passed the schema. |
| `dashboard/src/contexts/AuthContext.tsx` | On every `validateToken()` round-trip, re-derive role/tier from the validated server response — do not trust the cached localStorage values for role/tier checks. |
| `dashboard/src/api/__tests__/client.test.ts` | Forged-role test: write `{role:'system_admin'}` to localStorage → getUser returns null. |

### Acceptance criteria

- [ ] An attacker who writes a forged `user` object to localStorage cannot
      pass any client-side role check — `getUser()` returns null until the
      next server `validateToken` round-trip.
- [ ] `role` and `tier` for nav/route gating are sourced from the
      validated server response, not the cached object.
- [ ] All existing `client.test.ts` tests pass.

### Gotchas

- **This does not close CRIT-011 in full** — JWT is still in localStorage
  and any XSS still exfiltrates a working bearer token. The real fix is
  HttpOnly cookies (backend + frontend coordinated change). Document the
  remaining gap in the PR body and link a follow-up issue.
- Existing R2 changes use `useAuth().productRole`. Make sure the new
  schema permits the projected role value (or document that productRole
  is derived after schema validation).

### Effort

2–3 engineer-days.

---

## PR #8 — Stripe `subscription.updated` writes `org.tier`

**Closes:** CRIT-006.

### Files touched

| File | Change |
|---|---|
| `policy_engine/routes/billing/clinic.py` (around `_handle_subscription_updated`) | Extract tier from `subscription['items']['data'][0]['plan']['metadata']['tier']` (or `product.metadata.tier`). Write `org.tier` when `status in ('active', 'trialing')` AND the new tier differs. Audit the change. |
| `policy_engine/services/billing/tier_resolver.py` (new) | Pure function: `resolve_tier(stripe_subscription) -> TierKey | None`. Unit-testable without Stripe SDK. |
| `tests/billing/test_subscription_tier_propagation.py` (new) | Fixture: a Stripe `customer.subscription.updated` event with plan metadata `{tier: 'clinic_standard'}` → org.tier flips. |

### Acceptance criteria

- [ ] Subscriptions created via the Stripe customer portal (which fire
      `subscription.created` but no `checkout.session.completed`) correctly
      set `org.tier`.
- [ ] Plan changes (downgrade / upgrade) fire `subscription.updated` and
      `org.tier` follows.
- [ ] Idempotent: replaying the same event is a no-op (existing
      `billing_events.stripe_event_id` UNIQUE constraint is honoured).
- [ ] Status transitions to `canceled` / `unpaid` revert tier via the
      already-wired lifecycle worker (do not duplicate here).
- [ ] Test passes against the `stripe` SDK once it's installed in dev
      deps; tier_resolver unit tests pass with no Stripe SDK present.

### Gotchas

- The `stripe` SDK is **not** in dev deps. 13 billing tests are currently
  skipped. Either: (a) add `stripe` to dev deps in `requirements-dev.txt`,
  or (b) write the resolver test against a fixture dict, not the real SDK.
  Recommended: do both — fixture dict for the unit, real SDK for the
  integration when dev deps land.
- Plan-metadata schema is a product decision: who sets `plan.metadata.tier`
  in Stripe? Document the contract in the PR body.

### Effort

2–3 engineer-days. Blocked on stripe SDK dev dep until the resolver is
written against fixture dicts.

---

## PR #9 — `organization_id NOT NULL` across multi-tenant tables

**Closes:** CRIT-010.

### Files touched

| File | Change |
|---|---|
| `alembic/versions/2026_NN_NN_NNNN-020_org_id_not_null.py` (new) | Per-table block: count NULLs → if any exist, FAIL the migration with a clear error pointing to the backfill script; else `ALTER COLUMN organization_id SET NOT NULL`. |
| `scripts/backfill_organization_id.py` (new) | Maps known-orphan rows to an "unknown" sentinel org, or to the row's natural owner if derivable (e.g. audit_logs.organization_id ← agents.organization_id where agent matches). Idempotent. |
| `policy_engine/models/*.py` (13 files) | Change `organization_id = Column(..., nullable=True)` → `nullable=False` on each affected model. **Do this in the same PR as the migration so the model and the schema match.** |
| Tables affected (per REVIEW.md DB-CRIT-003) | `audit_logs`, `prior_auth_records`, `alerts`, `hitl_reviews`, `shadow_ai_detections`, `scribe_audits`, `model_cards`, `bias_audits`, `revenue_cycle_audits`, `risk_scores`, `clinic_ai_tools`, `clinic_ai_observations`, `clinic_report_artifacts`. |
| `tests/migrations/test_migration_020_org_not_null.py` (new) | Asserts the migration refuses to run with orphan NULLs; asserts model `__table__.columns['organization_id'].nullable is False` after upgrade. |

### Acceptance criteria

- [ ] Migration is **safe** — it surveys NULL counts first and refuses to
      proceed if any exist. Operators must run the backfill script and
      re-run.
- [ ] All 13 models have `nullable=False` after this PR.
- [ ] Foreign keys on critical tables change from `ON DELETE SET NULL` to
      `ON DELETE RESTRICT` (CRIT-010 recommendation). Audit-log retention
      currently relies on SET NULL — see PR #10 for the coordinated change.

### Gotchas

- **Coordinated with PR #10:** the alerts table has a bare `audit_log_id`
  String column (not a real FK). PR #10 converts it to a real FK with
  `ON DELETE SET NULL` — that needs to land **before** PR #9 changes
  the `audit_logs.organization_id` FK to `ON DELETE RESTRICT`.
- **PostgreSQL row-level security (RLS)** is the durable defence here.
  Out of scope for this PR but added to ARCH-FOLLOWUP in REVIEW.md.

### Effort

3–4 engineer-days. The bulk is the backfill survey and the per-table
test setup.

---

## PR #10 — Retention with legal-hold gate + archive durability

**Closes:** CRIT-008.

### Files touched

| File | Change |
|---|---|
| `alembic/versions/2026_NN_NN_NNNN-021_audit_legal_hold.py` (new) | (1) Add `legal_hold BOOLEAN NOT NULL DEFAULT FALSE` to `audit_logs`. (2) Convert `alerts.audit_log_id` from `String` to a real FK with `ON DELETE SET NULL`. (3) Add index on `(organization_id, timestamp)` if not already present. |
| `policy_engine/models/audit_log.py` | Add `legal_hold` column. |
| `policy_engine/models/alert.py` | Change `audit_log_id` to FK. |
| `policy_engine/services/audit_retention.py` | (1) Filter purge query by `legal_hold == False`. (2) Verify archive ETag round-trip **before** delete (S3) or filesystem flush+stat (local). (3) Use a single `archive_and_delete()` code path — remove the duplicate in `run_retention_policy`. (4) Honour a configurable retention floor with a hard minimum of 365 days (HIPAA-aware deployments override to 6 × 365 + grace). |
| `policy_engine/config.py` | Add `RETENTION_HARD_MIN_DAYS: int = 2190` (6 years) and `RETENTION_DAYS` (existing) with validation that `RETENTION_DAYS >= RETENTION_HARD_MIN_DAYS` when `HIPAA_MODE=true`. |
| `tests/test_audit_retention.py` | Extend: legal-hold row never purged; archive failure aborts delete; alert.audit_log_id is NULL (not dangling) after parent purge. |

### Acceptance criteria

- [ ] A row with `legal_hold = TRUE` is **never** purged regardless of age.
- [ ] Archive-backend ETag (S3) or stat-after-fsync (local) is verified
      before the row is deleted.
- [ ] Existing `alerts.audit_log_id` references are reset to NULL on the
      cascade, not dangling.
- [ ] `HIPAA_MODE=true` enforces ≥ 6 × 365 days retention; refuses to
      start with a shorter `RETENTION_DAYS`.

### Gotchas

- The retention sweep is a **scheduled job** running in-process. The
  startup-guard for `RETENTION_DAYS < hard min` must not break the
  scheduler — keep the abort path inside the job's `if HIPAA_MODE`
  branch and surface it via an alert, not via process exit.
- Backfilling `alerts.audit_log_id` from String→FK on a production DB:
  some rows may reference now-purged audit logs. Set those to NULL
  during the migration (the migration runs as a single transaction).

### Effort

3–4 engineer-days.

---

## PR #11 — Prior-auth chain `seq_no` + tail-deletion detection

**Closes:** CRIT-005.

### Files touched

| File | Change |
|---|---|
| `alembic/versions/2026_NN_NN_NNNN-022_prior_auth_seq_no.py` (new) | Add `seq_no BIGINT NOT NULL` to `prior_auth_records`. Backfill via window function (`ROW_NUMBER() OVER (PARTITION BY organization_id ORDER BY created_at)`). Add `UNIQUE (organization_id, seq_no)`. |
| `policy_engine/domain/finance/prior_auth.py` | (1) Include `seq_no` in `compute_record_hash` input. (2) `verify_chain` checks `seq_no` gaps and refuses to call a chain valid if `len(records) < previous_status.total_records`. |
| `policy_engine/services/prior_auth_chain.py` | Compare `len(records)` to previous `PriorAuthChainStatus.total_records`; decrease → CRITICAL alert. |
| `tests/test_prior_auth_chain_integrity.py` (new) | Three scenarios: (a) tail deletion is detected, (b) middle deletion is detected, (c) clean chain verifies. |

### Acceptance criteria

- [ ] Deleting the last N records reduces `len(records)` below the stored
      `total_records` → `verify_chain` returns `(False, 'tail_deletion')`.
- [ ] Deleting a middle record (already detected) still returns False with
      the original reason.
- [ ] Clean chain verifies True.
- [ ] Backfill on existing data is deterministic and idempotent.

### Gotchas

- Including `seq_no` in the hash changes the hash of every existing row.
  The migration must **recompute** every hash after backfill, **once**,
  and lock the chain afterwards. Document that this is a one-time
  migration; future inserts use the new hash schema.
- The "external anchor" recommendation (publish chain-tip hash to an
  append-only external log) is ARCH-FOLLOWUP — not in this PR.

### Effort

2–3 engineer-days.

---

## PR #12 — HITL audit-chain redesign (CRIT-002 + CRIT-003)

**Closes:** CRIT-002 (recompute-on-append) and CRIT-003 (timezone-format
mismatch).

This is the **largest** ticket. It is intentionally a single PR because
the two CRITs share the same surface — fixing one without the other
leaves the chain still non-operational.

### Files touched

| File | Change |
|---|---|
| `policy_engine/domain/clinical/hitl.py` | (1) `compute_hash` accepts a normalised UTC-naive ISO timestamp string; production callers must pass the same shape on both write and verify. (2) Add `previous_entry_hash` argument; remove the recompute path entirely. (3) `verify_audit_chain` iterates records and recomputes only the *expected* current hash from the *previous persisted* hash — never rewrites prior rows. |
| `policy_engine/routes/clinical/hitl.py` (`_append_audit_entry`) | New behaviour: read `last_entry.entry_hash`; compute new entry hash from it; INSERT the new row only; never UPDATE existing rows. Make the insert idempotent on `(review_id, action, actor_id, timestamp_normalised)` so retried writes don't double-append. |
| `alembic/versions/2026_NN_NN_NNNN-023_hitl_chain_append_only.py` (new) | (1) Replace empty-string default on `entry_hash` with no default and `NOT NULL`. (2) Add a CHECK constraint or trigger preventing UPDATE on `entry_hash`, `comments`, `action`, `old_status`, `new_status`, `actor_id`, `timestamp`. Postgres trigger; SQLite skip with documented gap. (3) Backfill: recompute hashes for existing chains under the new schema and write them once. |
| `policy_engine/models/hitl.py` | Make `entry_hash` `nullable=False`, no default. |
| `tests/clinical/test_hitl_chain_immutability.py` (new) | (a) Append; verify True. (b) Update prior comment via raw SQL on Postgres → next verify returns False. (c) Tz round-trip: append at write time, verify at read time → True. (d) Concurrent appends on the same chain: deterministic ordering, no duplicates. |
| `tests/clinical/test_hitl_chain_tz.py` (new) | Specifically exercises the CRIT-003 surface — every timestamp comparison uses the same shape. |

### Acceptance criteria

- [ ] An existing chain entry's `comments` cannot be modified without the
      verifier detecting it.
- [ ] `verify_audit_chain` returns True on a clean chain (refutes
      CRIT-003).
- [ ] `_append_audit_entry` never UPDATEs an existing row.
- [ ] Concurrent appends are serialised (DB row lock on the chain tip, or
      `INSERT ... RETURNING` against a `seq_no` per review).
- [ ] On Postgres, the BEFORE UPDATE trigger fires and refuses the update.
- [ ] On SQLite, the test suite documents the gap with `@pytest.mark.skip(
      reason="SQLite has no triggers fixture — Postgres-only enforcement")`.

### Gotchas

- This is the **highest-risk** PR in the plan. It changes the contract
  for every existing HITL row and the verifier behaviour. Mitigation:
  (1) full backup of `hitl_audit_entries` before the migration; (2)
  staging deploy with a synthetic chain first; (3) the migration runs
  the backfill in a single transaction.
- The recommendation in REVIEW.md mentions an **append-only audit-chain
  library** as ARCH-FOLLOWUP — pulling it out of `hitl.py` into a shared
  module would help CRIT-005 (PR #11) and CRIT-002 share code. Out of
  scope for this PR; flag in PR body for the follow-up.
- Database triggers in SQL are non-trivial to test. Use `pg_tmp` or
  `testcontainers-postgres` in the test config — neither is currently a
  dev dep. Add `testcontainers[postgres]` and an opt-in `--pg` pytest
  flag.

### Effort

1–2 engineer-weeks. Adversarial review (security + healthcare) required
before merge.

---

## Cross-cutting work outside the 12 PRs

These are not standalone CRITs but they unblock or harden multiple PRs:

### W-1: Install missing dev deps

**Affects:** PR #8 (stripe), CRIT-008 testing (freezegun), PR #12
(testcontainers-postgres).

**Action:** add to `requirements-dev.txt`:

```
stripe>=8.0.0,<13.0.0
freezegun>=1.4.0,<2.0.0
testcontainers[postgres]>=4.0.0,<5.0.0
```

The 13 pre-existing failing tests should collect and pass once `stripe`
is installed. Verify in CI.

### W-2: PostgreSQL CI lane

**Affects:** every PR that adds a migration, plus PR #12 (trigger tests).

**Action:** add a CI matrix entry that boots a Postgres 16 container and
runs `alembic upgrade head` against it. Today the suite is SQLite-only —
PR #5, #9, #10, #11, #12 all add migrations whose intended target is
Postgres, so SQLite-only CI is insufficient.

### W-3: PHI-corpus dev fixture

**Affects:** the eventual A2/A3 (paste interception + sanitise) follow-up
work in `plans/clinical-shield-v1.md`. Not a CRIT, but the test infra
needed for those features should be set up alongside this remediation so
they don't bottleneck the v1.0 store submission.

**Action:** `tests/fixtures/phi_corpus.json` seeded from MITRE/synthea
synthetic data. Two corpora: structured-PHI and narrative-PHI, gated
separately per RR-4 / HEALTH-1.

---

## Verification gates per PR

Every PR in this plan must pass, before merge:

| Gate | Tool / command |
|---|---|
| Unit tests for the changed surface | `pytest <scope> -v` |
| Regression suite | `pytest --ignore=tests/billing --ignore=tests/services_clinic` (until W-1 lands; then full `pytest tests/`) |
| Type checking (dashboard PRs) | `npx tsc --noEmit` |
| Lint | `bandit -r policy_engine sentinel`, `ruff check` |
| Migration round-trip | `alembic upgrade head → downgrade -1 → upgrade head` on a copy of the dev DB |
| Coverage on touched modules | ≥ 85 % per `rules/common/testing.md` |
| Adversarial review | `code-reviewer` agent; PR #2, #3, #4, #12 also `security-reviewer`; PR #3 and #12 also `healthcare-reviewer` |

---

## What "ready for deployment without caveat" means after these 12 PRs

When all 12 PRs land and W-1 / W-2 / W-3 are complete:

- The 13 CRITICAL findings in `REVIEW.md` are closed.
- The HIGH-rated tenancy items that share surfaces with CRIT-001/004 are
  also closed (free with the same fixes).
- The audit chains provide tamper evidence end-to-end.
- The platform supports multi-tenant deployment and HIPAA-touching
  deployments **at the technical layer**. Compliance attestation
  (BAA, risk assessment, SOC 2, formal pen test) is **separate** and not
  in scope of this plan.
- Coverage is back above the 80 % floor.

The remaining HIGH/MEDIUM/LOW tail (21 + 24 + 15 = 60 items) is
documented in `REVIEW.md` and should be tackled in a Pass 2 sweep
post-deployment, prioritised by `READINESS_ASSESSMENT.md` Section
"Recommended remediation order".

---

*End of plan.*
