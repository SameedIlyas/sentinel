# fix/security-and-logic-pass-1 — auto-applied HIGH remediations

Pass 1 of the REVIEW.md audit. Closes **10 HIGH** findings in 10 atomic Conventional-Commits commits. All 13 CRITICAL and 22 remaining HIGH findings are **🔴 HUMAN-REVIEW-REQUIRED** or hit an explicit stop condition (schema change to a tenant-scoped table, audit-log shape change, `/v1/clinic/*` route, public API shape, browser-extension transmit shape) and are documented as deferred in `REVIEW.md` with the regulatory clause that gates each one.

> Open as **Draft PR** — do not merge until the deferred CRITICAL/HIGH items are triaged.

---

## Triage — before vs. after

| Severity | Before | Closed in this pass | Deferred (HUMAN-REVIEW / stop-condition) |
|---|---:|---:|---:|
| CRITICAL | 13 | 0 | **13** |
| HIGH | 31 | **10** | 21 |
| MEDIUM | 24 | 0 | 24 |
| LOW | 15 | 0 | 15 |
| **Total** | **83** | **10** | **73** |

CRITICAL count is unchanged on purpose — each one cites HIPAA §164.312, §164.502, §164.504, FDA 21 CFR Part 11 §11.10(e), CMS-0057-F, MDR PSUR, or EU AI Act Art.9/10/12 and requires human sign-off before remediation.

---

## What changed (file:line · exploit summary)

1. **HIGH-032** — `policy_engine/services/url_validator.py:21` (SSRF). `PRIVATE_IPV6` only blocked `::1/128`. ULA `fc00::/7`, link-local `fe80::/10`, IPv4-mapped `::ffff:0:0/96` (including `::ffff:169.254.169.254` for AWS IMDS), NAT64 `64:ff9b::/96`, Discard `100::/64`, and multicast addresses now blocked. *(commit `87cc6ae`)*
2. **HIGH-015** — `policy_engine/services/slack_service.py:66-91` (event-loop DoS). Sync `requests` + `time.sleep` backoff blocked the uvicorn event loop up to `retry_attempts × timeout` seconds whenever Slack was degraded — exactly during the incident the alert was warning about. `send_alert` now detects a running asyncio loop and offloads via `loop.run_in_executor`, returning fire-and-forget. Sync callers keep old semantics. *(commit `283a982`)*
3. **HIGH-016** — `policy_engine/routes/policy_check.py:294-298` (info disclosure). Fail-safe `/v1/policy/check` response embedded `str(e)` verbatim in `reason` and `metadata.error`, leaking DB connection strings, ORM column names, file paths, stack-trace fragments to every AI agent that triggered an exception. Response field names and types unchanged; content is now a generic message plus an opaque `error_id` for log correlation. *(commit `4650bab`)*
4. **HIGH-004** — `policy_engine/routes/admin/transparency.py:300-346` (cross-tenant write). `update_transparency_record` and `publish_transparency_record` only checked the role bit. An ORG_ADMIN at org A could PUT or POST publish against any org B record. New `_enforce_record_tenancy` returns 404 for non-SYSTEM_ADMIN cross-org access. *(commit `5e5752b`)*
5. **HIGH-014** — `alembic/versions/2024_02_12_0000-005_add_organizations.py:59-61` (migration safety). `downgrade()` dropped tables without dropping the five named indexes; a partial failure left orphan indexes that the table-existence guard in `upgrade()` then silently skipped re-creation around. Now drops every index child→parent with `if_exists=True`. *(commit `7e7d203`)*
6. **HIGH-031** — `clinic-extension/options.js:15-17` (token exfiltration). Any string typed into the endpoint field was stored verbatim and used in `fetch()` with the `X-Clinic-Extension-Token` header — a rogue admin or socially-engineered user could redirect every observation POST (token included) to an attacker-controlled host or even `javascript:`. New `validateEndpoint()` enforces an http/https allowlist, requires a parseable URL with hostname, and rejects URLs containing credentials. The on-wire payload from `background.js` is unchanged. *(commit `bdfa8d4`)*
7. **HIGH-025** — `dashboard/src/api/client.ts:93-96` (silent logout). `JSON.parse(userStr)` had no try/catch; a corrupt `user` entry (browser-quota error, manual edit, third-party extension) threw SyntaxError out of `getUser()`, was caught silently by `AuthContext.initAuth`, and logged the user out with no error — and the bad entry persisted, so every reload also failed. Now wrapped in try/catch with `clearUser()` on failure. *(commit `62588b2`)*
8. **HIGH-026** — `dashboard/src/contexts/AuthContext.tsx:184`, `dashboard/src/components/layout/AppLayout.tsx:121-122` (silent client-side gate failure). Both sites cast `user?.tier as TierKey`, suppressing every TypeScript guarantee. A backend response carrying an unknown tier string (e.g. a newly-rolled SKU `clinic_pro`) passed the cast unchanged but every `NAV_SECTIONS.tierAllowed()` returned false, leaving the user with a blank sidebar and no error. New `resolveTier(raw: unknown): TierKey` in `@/types` validates against the four canonical tiers and falls back to `'enterprise'`. *(commit `d533d8e`)*
9. **HIGH-027** — `dashboard/src/hooks/useWebSocket.ts:39-93` (duplicate WS connections). `connect`'s `useCallback` listed `onMessage/onError/onOpen/onClose` in its deps. Parent components pass plain (non-memoised) handlers (e.g. `Dashboard.tsx:66-72`), so every parent render produced a new handler identity, changed `connect`'s identity, fired the binding `useEffect`, and opened a fresh socket before the old one finished closing. Callbacks are now stored in refs; `connect` depends only on `[url, reconnectInterval, reconnectAttempts]`. Regression test renders the hook with a non-memoised onMessage, bumps parent state 10 times, asserts exactly 1 socket opens. *(commit `9cac3d5`)*
10. **HIGH-029** — `dashboard/src/pages/Dashboard.tsx:87-91` (data race). 60s `setInterval(fetchMetrics)` ran unconditionally even when the WebSocket was already pushing live `metrics_update` events. REST polls raced the stream and frequently overwrote fresh push data with an older REST snapshot whose response landed last. Split into two effects: initial mount fetch (always), polling interval gated on `!isConnected`. *(commit `1de0887`)*

Plus `docs(review)` commit `58e7d9a` appending the per-finding Deferred table to `REVIEW.md`.

---

## Deferred — human-review required

Full per-finding table with regulatory clauses lives in `REVIEW.md` under "Pass 1 Remediation Status". Headline summary:

- **All 13 CRITICAL** findings — every one cites HIPAA §164.312, §164.502, §164.504, FDA 21 CFR Part 11, CMS-0057-F, MDR PSUR, or EU AI Act and requires human sign-off. Several also hit stop conditions:
  - **CRIT-003, CRIT-005, CRIT-008, CRIT-010** — schema change to a tenant-scoped table or audit-log shape change.
  - **CRIT-006** — public API shape change to `/v1/billing/clinic/webhook`.
  - **CRIT-013** — public API shape change to the dashboard WebSocket auth.
- **21 of 31 HIGH** findings deferred. Notable stop conditions:
  - **HIGH-006, HIGH-007** — `/v1/clinic/baa/accept`, `/v1/clinic/settings/practice` (both `/v1/clinic/*`).
  - **HIGH-003** — `/v1/transparency` public API shape change (adding auth).
  - **HIGH-009, HIGH-011, HIGH-012, HIGH-017, HIGH-022, HIGH-023** — schema changes to tenant-scoped or audit-log tables.
  - **HIGH-028** — broad refactor across every ApiClient HTTP method signature (carves out "no refactors" rule).
  - **HIGH-024, HIGH-030** — paired with deferred CRITICALs (CRIT-011, CRIT-013).

ARCH-FOLLOWUP items (10) recorded in `REVIEW.md`. None are required to close individual CRITICALs but they are the durable structural fixes (append-only audit-chain library, `TierStateMachine`, Postgres RLS, DB-level append-only triggers).

---

## Test plan

- [x] **TDD discipline:** every fix is `failing test → minimal patch → green`. 10 new test files added under `tests/` and `dashboard/src/**`.
- [x] **`pytest` slice:** `tests/test_url_validator_ssrf.py`, `test_slack_async_nonblocking.py`, `test_policy_check_failsafe_redaction.py`, `test_transparency_tenant_isolation.py`, `test_migration_005_downgrade.py`, `test_extension_options_validation.py`, `test_startup_guards_smoke.py` → **40 passed**.
- [x] **`pytest tests/test_phi_scan_meta.py tests/test_extension_manifest.py`** (CI PHI meta-scan + manifest hygiene) → **7 passed, 1 skipped**.
- [x] **`pytest tests/test_policy_evaluation.py tests/test_phase4_admin.py::TestTransparencyRoutes tests/test_transparency_auto_service.py tests/test_alert_service.py`** (regression on touched modules) → **all green** (28 + 21 + 38 pass counts confirmed across earlier runs).
- [x] **`npx vitest run`** on the four new dashboard test files → **28/28 passed**.
- [x] **`npx tsc --noEmit`** (dashboard) → **0 errors**.
- [x] **`bandit -r policy_engine sentinel`** → **0 Medium/High** (20 Low, all pre-existing, not in scope).
- [x] **Alembic round-trip** on temp SQLite DB → `upgrade head` clean (17 migrations); `upgrade 005 → downgrade 004 → upgrade 005` round-trip clean on the migration I patched.
- [x] **Startup guards:** `tests/test_startup_guards_smoke.py` (4 tests) verifies `lifespan()` still aborts on empty / short / known-weak SECRET_KEY and on `CORS_ALLOW_ALL_ORIGINS=True` in production.
- [ ] **Full `pytest tests/` with coverage:** running at PR open; preliminary result will be posted in a follow-up comment once it completes (1182 tests + coverage instrumentation takes ~20 min on this hardware). Already validated focused slices listed above.
- [ ] **Full `npm --prefix dashboard test`:** 121 passed / 19 failed (12 files) — pre-existing failures unrelated to this branch. `resolveTier` actually **reduces** failures from 37 → 19 because downstream nav filters no longer silently empty.
- [ ] **Playwright E2E:** no `playwright.config.*` and no `e2e/` directory in the repo. `@playwright/test` is a devDep but no suite is wired up — not blocking this PR.
- [ ] **Pre-existing dev-dep gaps (not in scope for this PR):**
  - `freezegun` missing — `tests/billing/test_subscription_cancellation_e2e.py`, `tests/services_clinic/test_clinic_retention.py`, `tests/services_clinic/test_subscription_lifecycle.py` fail at collection.
  - `stripe` SDK missing — `tests/billing/test_webhook_handlers.py` (7 tests) fails at the webhook-signature check.
  - Verified by `git stash && pytest …` on `main`: identical failures before this branch.
- [ ] **Manual QA recommended before merge:**
  - Boot Policy Engine against a real PostgreSQL; confirm startup guards abort on weak SECRET_KEY and on `CORS_ALLOW_ALL_ORIGINS=True`. (Smoke test covers the lifespan generator; live boot is the next layer.)
  - Seed `enterprise` and `clinic_basic` orgs; walk every route under each persona; capture screenshots and diff against a baseline.
  - Replay a Stripe `checkout.session.completed` event through `/v1/billing/clinic/webhook` (requires `stripe` SDK install + Stripe CLI or webhook fixture); confirm `org.tier` flips exactly once on duplicate delivery (the `billing_events.stripe_event_id` UNIQUE constraint enforces idempotency at the schema level — but CRIT-006 means `subscription.updated` retries are still not driven through tier).

---

## Branch

`fix/security-and-logic-pass-1` off `main`. 11 commits ahead. Not yet pushed to remote — see "Open this PR" note below.

## Commits

```
58e7d9a docs(review): record pass 1 remediation status + deferred list
1de0887 fix(dashboard): suppress polling while WebSocket is connected (HIGH-029)
9cac3d5 fix(dashboard): stabilise useWebSocket callbacks via refs (HIGH-027)
d533d8e fix(dashboard): runtime-validate TierKey with resolveTier (HIGH-026)
62588b2 fix(dashboard): guard JSON.parse in ApiClient.getUser (HIGH-025)
bdfa8d4 fix(security): validate extension endpoint URL before saving (HIGH-031)
7e7d203 fix(migration): drop named indexes in 005 downgrade (HIGH-014)
5e5752b fix(security): enforce tenancy on transparency update/publish (HIGH-004)
4650bab fix(security): redact str(exc) from /v1/policy/check fail-safe response (HIGH-016)
283a982 fix(security): offload Slack send to executor inside event loop (HIGH-015)
87cc6ae fix(security): expand SSRF IPv6 blocklist (HIGH-032)
```
