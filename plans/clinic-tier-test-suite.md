# Plan — Clinic-Tier Test Suite + Full System Regression

**Status:** REVIEWED v2 — adversarial review fixes applied (C1–C5, H1–H6, plus M/L)
**Author:** automated (blueprint skill)
**Created:** 2026-05-10
**Branch base:** `main`
**Repo:** `SameedIlyas/sentinel`

---

## Objective

Deliver a production-grade test suite for the recently shipped Clinic tier
(commits `07572e9..HEAD`) plus a full-system regression sweep, with HIPAA +
GDPR safety guarantees baked in. Coverage target: ≥ 80 % of files changed
since `07572e9`. Acceptance: zero CRITICAL/HIGH from `security-reviewer`,
zero PHI in fixtures/logs/screenshots, all journeys green.

## Locked scope (from user clarifications)

| Question | Answer |
|---|---|
| SDKs in scope | Sentinel internal SDK + Anthropic Messages API + Stripe SDK |
| "Agent" | Synthetic clinic-admin AI agent driving the API via Claude Agent SDK |
| "Account" | Test clinic org via `/v1/clinic/onboarding`, in-memory test DB |
| Stripe | Signed-fixture webhooks (HMAC-locally-signed); no real Stripe sandbox |
| Test scope | Full system regression |

---

## Surface inventory

### Backend (Python / FastAPI)
- **Models** (clinic): `policy_engine/models/clinic.py` — `ClinicAiTool`, `ClinicAiObservation`, `BillingEvent`, `ClinicExtensionToken`, `ClinicReportArtifact`
- **Migrations:** `alembic/versions/016_clinic_tier.py`, `017_clinic_compliance.py`
- **Services:** `clinic_alert_translator`, `clinic_audit`, `clinic_pdf_report`, `clinic_policy_templates`, `clinic_retention`, `phi_text_check`, `tier_filter`, `subscription_lifecycle`
- **Routes (clinic):** `onboarding`, `settings`, `tools`, `policy_templates`, `alerts`, `dashboard`, `shadow_ai`, `baa`, `reports`
- **Routes (billing):** `routes/billing/clinic.py`
- **Billing module:** `billing/plans.py`, `billing/stripe_client.py`

### Frontend (React / TS)
- 11 clinic pages under `dashboard/src/pages/clinic/**`
- New `i18n/` dir, navigation + AuthContext changes
- Already has `@playwright/test` and `vitest` in devDependencies

### Extension
- `clinic-extension/` — `manifest.json`, `background.js`, `options.js` (no tests, no build)

### Existing test infra (reuse, do NOT rewrite)
- `tests/conftest.py` — sqlite in-memory, fixtures: `client`, `db_session`, `agent_api_key`, `admin_user_jwt`, `make_user_jwt`, `mock_redis`, `mock_slack`, `authed_client`
- `tests/.env.test` — already loaded before any `policy_engine` import
- `tests/sdk/` — existing SDK adapter test pattern

### Conftest model registration (already covered transitively — verify, do NOT add)
`policy_engine/models/__init__.py:17` already executes `from policy_engine.models.clinic import (...)`, so any conftest import of `policy_engine.models.*` triggers clinic-table registration with `Base.metadata`. **Therefore the "conftest gap" is empirical false** — verify with `python -c "from tests.conftest import Base; print({'clinic_ai_tools','billing_events'} <= set(Base.metadata.tables))"`. If True (expected), Phase 1 does NOT add a duplicate import. If False, that is itself a regression to fix.

### Merge order (mandatory)
`Phase 1` → `(Phase 2, 3, 4, 6 — any order, parallel)` → `Phase 5` → `Phase 7`. No PR may merge into `main` without all parallel siblings green. Phase 7 cannot start until 2/3/4/5/6 are all merged.

---

## Dependency graph

```
                ┌────────────────────────────────────────┐
                │ Phase 1 — Foundation (BLOCKING ALL)    │
                │  conftest fixes, fixture factories,     │
                │  test tree, .env.test additions         │
                └────────────────────┬───────────────────┘
                                     │
        ┌──────────────┬─────────────┼──────────────┬──────────────┐
        ▼              ▼             ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
  │ Phase 2  │  │ Phase 3  │  │ Phase 4  │  │ Phase 6  │  │ (Phase 1     │
  │ Backend  │  │ Billing  │  │ SDK      │  │ Extension│  │  also unblocks│
  │ unit +   │  │ + Stripe │  │ harness  │  │ + regres-│  │  Phase 5)    │
  │ integ    │  │ webhook  │  │ + agent  │  │ sion     │  │              │
  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────┘
       │             │             │             │
       └─────────────┴──────┬──────┴─────────────┘
                            ▼
                   ┌──────────────────┐
                   │ Phase 5 — UI E2E │   (depends on Phase 2 stable backend)
                   └────────┬─────────┘
                            ▼
                   ┌──────────────────┐
                   │ Phase 7 — CI +   │   (depends on ALL)
                   │ coverage + audit │
                   └──────────────────┘
```

**Parallelism:** Phases 2, 3, 4, 6 are independent after Phase 1 — different test trees, no shared writes. Phase 5 needs Phase 2's backend test fixtures stable (it reuses the `client` + `clinic_org` fixtures). Phase 7 is the closer.

---

## Phase 1 — Foundation & Fixtures

**Branch:** `tests/phase-1-foundation`
**Model tier:** default (Sonnet)
**Estimated tool calls:** 30–50

### Context brief (cold-start safe)
The repo at `C:\Users\Sameed\Documents\Devotrex\YC` has an existing pytest suite under `tests/` with sqlite in-memory infrastructure (StaticPool, single shared connection). The new Clinic tier shipped between `07572e9` and HEAD. Clinic models are ALREADY registered with `Base.metadata` transitively via `policy_engine/models/__init__.py:17`, which imports the clinic module at package init — so the autouse `_db_tables` fixture creates clinic tables today (verify before changing anything).

**Imports needed in this phase:**
- `from policy_engine.models import clinic` (verification only)
- `from policy_engine.models.organization import Organization, TIER_CLINIC_BASIC, TIER_CLINIC_STANDARD, TIER_CLINIC_MULTI_SITE, is_clinic_tier`
- `from policy_engine.models.user import User, UserRole`
- `from policy_engine.auth.jwt_utils import create_access_token, get_password_hash`
- `from policy_engine.services.phi_text_check import scan_for_phi`

### Tasks
1. **Verify (do not blindly add) clinic-model registration:** run the verification command above. If clinic tables already in `Base.metadata`, add no import. If somehow missing, add `from policy_engine.models import clinic as _clinic  # noqa: F401, E402` defensively. Either branch is committed with a one-line comment citing the verification result.
2. Create directory tree:
   - `tests/clinic/` — `__init__.py`, `test_routes_*.py` placeholders
   - `tests/billing/` — `__init__.py`, `test_webhook_*.py`, `test_plans.py`
   - `tests/services_clinic/` — `__init__.py`, `test_*.py` per service
   - `tests/sdk_harness/` — `__init__.py` (extends existing tests/sdk/)
   - `tests/agent/` — `__init__.py`, `test_clinic_admin_agent.py`
   - `tests/factories/` — `__init__.py`, `clinic.py`, `billing.py`, `phi_safe.py`
3. Create `tests/factories/clinic.py` with:
   - `make_clinic_org(db, tier="clinic_standard", baa_signed=True) → Organization`
   - `make_clinic_admin(db, org) → (User, jwt_token)`
   - `make_clinic_tool(db, org, **overrides) → ClinicAiTool`
   - `make_clinic_observation(db, org, **overrides) → ClinicAiObservation`
   - `make_billing_event(db, org, event_type, status="processed") → BillingEvent`
4. Create `tests/factories/phi_safe.py` with HIPAA Safe-Harbor synthetic strings: clinic names, tool descriptions, test addresses (state/city only, no street). NEVER any pattern matched by `phi_text_check._PATTERNS`.
5. Create `tests/factories/billing.py` with:
   - `make_stripe_event(event_type, **overrides) → dict` — minimal Stripe event JSON
   - `sign_webhook_payload(payload: bytes, secret: str, ts: int|None=None) → str` — produces Stripe-compatible `t=...,v1=...` header
6. Append to `tests/.env.test`:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_test_local_only_do_not_use_in_prod
   STRIPE_SECRET_KEY=sk_test_PLACEHOLDER_no_network_calls
   STRIPE_PAYMENT_LINK_CLINIC_BASIC=https://buy.stripe.com/test_basic
   STRIPE_PAYMENT_LINK_CLINIC_STANDARD=https://buy.stripe.com/test_standard
   STRIPE_PAYMENT_LINK_CLINIC_MULTI_SITE=https://buy.stripe.com/test_multisite
   ANTHROPIC_API_KEY=sk-ant-test-PLACEHOLDER
   CLINIC_LIFECYCLE_AUTO=false
   CLINIC_RETENTION_AUTO=false
   CLINIC_PDF_AUTO=false
   ```
   Rationale: turning the autostart schedulers OFF in tests prevents the lifespan event from firing background jobs against the test DB.
7. Add `tests/conftest.py` shared fixtures:
   - `clinic_org` — yields a `clinic_standard` org with BAA signed
   - `clinic_admin_jwt` — yields `(jwt, user, org)` triple
   - `clinic_authed_client` — `client` with the JWT pre-injected
   - `signed_webhook(event_type, **overrides)` — factory fixture returning `(body_bytes, signature_header)`
8. Add pytest markers in `pyproject.toml` `[tool.pytest.ini_options]`:
   ```
   markers = [
     "clinic: clinic-tier tests",
     "billing: billing/Stripe tests",
     "sdk: SDK harness tests",
     "agent: synthetic agent tests",
     "regression: full-system regression",
     "slow: > 1s individual test",
   ]
   ```
9. Extend **`[project.optional-dependencies].test`** in `pyproject.toml` (single source of truth — do NOT create `requirements-test.txt`) with: `stripe>=8.0`, `anthropic>=0.39`, `respx`, `pytest-cov>=4.1`, `freezegun>=1.4`, `pytest-randomly>=3.15`, `diff-cover>=9.0`, `pdfplumber>=0.10`, `presidio-analyzer>=2.2; python_version>="3.10"`, `presidio-anonymizer>=2.2; python_version>="3.10"`. **Do NOT add** `pytest-recording` (cassettes risk PHI capture) or `claude-agent-sdk` (Phase 4 hand-rolls a deterministic state machine instead — see Phase 4).
10. Create `TEST_PLAN.md` skeleton at repo root listing all phases + acceptance criteria.

### Files affected
- **Edit:** `tests/conftest.py`, `tests/.env.test`, `pyproject.toml`
- **Create:** the directory tree + `tests/factories/*` + `requirements-test.txt` + `TEST_PLAN.md`

### Verification
- `pytest --collect-only tests/clinic tests/billing tests/services_clinic` — must collect without errors (placeholders allowed).
- `pytest tests/test_health.py` — existing test still passes (no regression).
- `python -c "from policy_engine.models import clinic; print(clinic.ClinicAiTool.__tablename__)"` — prints `clinic_ai_tools`.
- All new fixtures load via `pytest --fixtures tests/clinic`.

### Exit criteria
- Conftest creates all clinic tables in test DB.
- Factories generate PHI-safe synthetic data only (verified by running `phi_text_check.scan_for_phi` on every factory output → must return None for every field).
- All schedulers disabled in test env.
- Existing test suite still 100 % green.

### Rollback
- Single revert of the Phase 1 PR. No data migration involved.

### Commit message
```
test(infra): scaffold clinic-tier test foundation

- Register clinic models with Base.metadata in conftest
- Add clinic/billing/services_clinic/sdk_harness/agent test trees
- PHI-safe factories per HIPAA Safe Harbor
- Stripe webhook signing helper for local fixtures
- Disable schedulers in .env.test
- Add pytest markers for clinic/billing/sdk/agent/regression
```

---

## Phase 2 — Backend unit + integration tests (Clinic)

**Branch:** `tests/phase-2-backend`
**Depends on:** Phase 1
**Model tier:** default (Sonnet) for routes; default for services
**Parallelizable:** with Phase 3, 4, 6
**Estimated tool calls:** 80–120

### Context brief
Cover every public service function and every clinic route with FastAPI `TestClient`. Backend uses sqlite in-memory; the existing `client` fixture handles dependency overrides. Auth: clinic routes use JWT (via `get_current_user`). The recent fix in commit 4421206 (policies route) added `JWT or API key` acceptance — verify both paths. Tier gating: every clinic route depends on `require_clinic_tier` or `require_clinic_tier_with_baa`; verify 403 when called from an enterprise-tier user.

### Tasks
1. **Service unit tests** — one file per service:
   - `test_phi_text_check.py` — table-driven over `_PATTERNS`. For each pattern: positive sample (synthetic), negative sample (looks-similar-but-not). Verify `reject_if_phi_present` raises `HTTPException(422)` with `error="phi_in_freetext"` and message NEVER echoes the matched text.
   - `test_tier_filter.py` — every dependency: enterprise user → 403 on clinic gate; clinic-no-baa → 403 on `_with_baa` gate; clinic-with-baa → passes; multi-site min-tier → basic 403, standard 403, multi-site OK.
   - `test_subscription_lifecycle.py` — table cases: org with `subscription_status="canceled"` and `current_period_end < now` → reverted to enterprise; `current_period_end > now` → still clinic; `subscription_status="active"` canceled with no end → reverted defensively. Idempotency: running twice reverts once.
   - `test_clinic_alert_translator.py` — enterprise-language alert → clinic-language. Snapshot test on representative alerts.
   - `test_clinic_pdf_report.py` — generate PDF from synthetic data; assert PDF bytes start with `%PDF-`; assert no PHI patterns leak into the rendered text via `pdfplumber`.
   - `test_clinic_policy_templates.py` — list templates; load each by id; missing id → 404.
   - `test_clinic_audit.py` — append-only behavior; ordering; tamper detection if present.
   - `test_clinic_retention.py` — synthetic old observations → swept; recent → preserved.
2. **Route integration tests** — file per route module under `tests/clinic/`:
   - `test_routes_onboarding.py` — POST `/v1/clinic/onboarding` happy path; idempotency (second call same org → 409 or no-op per spec); enterprise tier user → 403.
   - `test_routes_settings.py` — GET/PUT practice, compliance, billing. PHI in free-text → 422 with `error="phi_in_freetext"`.
   - `test_routes_tools.py` — CRUD; tool cap enforcement (basic=10, standard=25, multi-site=75); risk_level enum validation.
   - `test_routes_policy_templates.py` — list; load.
   - `test_routes_alerts.py` — list, resolve, ack.
   - `test_routes_dashboard.py` — summary contract: keys present, no PHI in any string field.
   - `test_routes_shadow_ai.py` — observation ingest from extension; `ClinicExtensionToken` auth path.
   - `test_routes_baa.py` — sign BAA; status; signing flips `org.hipaa_baa_signed`.
   - `test_routes_reports.py` — request generate; download artifact; auth (enterprise → 403).
3. **Auth tests (corrected — clinic routes are JWT-only):**
   - For each clinic route: assert 401 when called with no auth header at all.
   - For each clinic route: assert 401 when called with only an `X-API-Key` header (no JWT). This pins the *current* contract that clinic routes do NOT accept API keys — drift toward accepting them is a security regression that must be a deliberate decision, not silent.
   - For each clinic route: assert 200/expected-response with valid clinic-admin JWT.
   - The `JWT-or-API-key` parametrize **only** applies to `routes/policies` (per fix 4421206) and is out of scope for this phase.
4. **Migration tests** — `tests/clinic/test_migrations.py`:
   - Use `pytest-postgresql` or `testcontainers-python` to boot a real Postgres for the migration tests (CI must install Docker). No sqlite fallback — migrations are infrastructure code; they must run on the real engine.
   - Run `alembic upgrade head`; assert 016 + 017 tables present with expected columns/indexes/constraints.
   - `alembic downgrade -2`; assert tables removed.
   - `alembic upgrade head` again; idempotent.
   - Verified migrations 016 + 017 contain no JSONB/ARRAY/citext today, but locking in Postgres execution prevents future drift from being silently accepted.

### Files affected
- **Create:** ~18 new test files under `tests/clinic/` and `tests/services_clinic/`

### Verification
```
pytest tests/services_clinic tests/clinic -v
pytest --cov=policy_engine.routes.clinic --cov=policy_engine.services.clinic_alert_translator \
       --cov=policy_engine.services.phi_text_check --cov=policy_engine.services.tier_filter \
       --cov=policy_engine.services.subscription_lifecycle --cov-report=term-missing
```

### Exit criteria
- All new tests green.
- Per-file coverage ≥ 80 % on every file changed since `07572e9` in `policy_engine/services/clinic_*.py`, `phi_text_check.py`, `tier_filter.py`, `subscription_lifecycle.py`, `routes/clinic/*.py`.
- No PHI strings appear in any test fixture (run `phi_text_check.scan_for_phi` over every factory output in a meta-test).
- Existing test suite still green.

### Rollback
- Revert PR. Tests are additive only.

### Commit
```
test(clinic): unit + integration tests for clinic-tier backend

- 8 service-level test files (phi_text_check, tier_filter, ...)
- 9 route-level integration files covering JWT + API key auth
- Tier-gating 403 paths between enterprise/clinic
- Migration 016 + 017 forward+downgrade
```

---

## Phase 3 — Billing & Stripe webhook tests

**Branch:** `tests/phase-3-billing`
**Depends on:** Phase 1
**Parallelizable:** with Phase 2, 4, 6
**Estimated tool calls:** 40–60

### Context brief
`policy_engine/routes/billing/clinic.py` exposes `/v1/billing/clinic/{plans,payment-link,portal,webhook}`. Webhook signature verification uses `stripe.Webhook.construct_event` when `STRIPE_WEBHOOK_SECRET` is set (production path). In dev/test it short-circuits to `True` — but our tests should exercise the **real** signature path because that is the production code. Strategy: set `STRIPE_WEBHOOK_SECRET` in `.env.test`, sign every fixture with it, and assert that an unsigned/incorrectly-signed body returns 400. PII redaction (`_redact_event_for_audit`) drops `address`, `phone`, `tax_ids`, `tax_exempt`, `tax_id_data`, and replaces `payment_method_details` with `{type}` — assert these on persisted `BillingEvent.payload`.

### Tasks
1. `tests/billing/test_plans.py` — `get_plan`, `is_clinic_plan`, `stripe_payment_link` (with and without env vars set).
2. `tests/billing/test_stripe_client.py` — `get_stripe()` raises `StripeUnavailable` when env unset; returns module when set; `webhook_secret()` reads env.
3. `tests/billing/test_routes_plans.py` — GET `/clinic/plans`, GET `/clinic/payment-link?plan=clinic_basic`, 400 for unknown plan, 503 when env unset.
4. `tests/billing/test_routes_portal.py` — POST `/clinic/portal` — 409 when no `stripe_customer_id` on org; mock `stripe.billing_portal.Session.create` to return a fake URL; assert response shape.
5. `tests/billing/test_webhook_signatures.py`:
   - Valid signature → 200 with `{status: "processed", ...}` (or skipped if event not handled).
   - Missing signature header → 400 "Invalid signature".
   - Tampered body → 400.
   - Wrong secret → 400.
6. `tests/billing/test_webhook_idempotency.py` — replay same `event.id` → second call returns `{status: "skipped", reason: "duplicate"}`; only one `BillingEvent` row.
7. `tests/billing/test_webhook_handlers.py` — one parametrize per handler:
   - `checkout.session.completed` w/ `client_reference_id="clinic_standard"` and `metadata.org_slug` → org tier flips to `clinic_standard`, `stripe_customer_id` stored, `subscription_status="active"`.
   - `customer.subscription.updated` past_due → `subscription_status="past_due"`.
   - `customer.subscription.deleted` → `subscription_status="canceled"` AND `current_period_end` preserved (tier NOT immediately reverted — that's the lifecycle job's responsibility from Phase 2 tests).
   - `invoice.payment_failed` → `subscription_status="past_due"`, `last_failed_invoice_id` set.
   - `invoice.payment_succeeded` after past_due → `subscription_status="active"`, failure fields cleared.
   - Unhandled event type → `{status: "skipped"}` recorded.
8. `tests/billing/test_webhook_pii_redaction.py` — **cover the FULL `_REDACT_DETAIL_KEYS` tuple** (`address, phone, tax_ids, tax_exempt, tax_id_data`):
   - Build a fixture event with `customer_details: {address, phone, tax_ids, tax_exempt, tax_id_data, email, name}` AND top-level `data.object.{address, phone, tax_ids, tax_exempt, tax_id_data}` AND `payment_method_details: {card: {last4, fingerprint, ...}}`.
   - POST to webhook; query `BillingEvent.payload`; assert ALL FIVE redact keys are GONE in BOTH locations, `email`/`name` PRESENT, `payment_method_details == {type: ...}`.
   - **Mutation-contract test:** capture `original = copy.deepcopy(event)`; call `_redact_event_for_audit(event)` directly; assert `original != event` (mutation observed). This pins the in-place-mutation contract so a future refactor to "return a copy" surfaces as a test failure rather than silently double-redacting upstream callers.

10. `tests/billing/test_subscription_cancellation_e2e.py` — **end-to-end subscription cancellation lifecycle** (closes the gap between the webhook test and the lifecycle service test):
    - Use `freezegun.freeze_time("2026-05-10T00:00:00Z")` to anchor the clock.
    - Boot a clinic_standard org with `subscription_status="active"`.
    - POST a `customer.subscription.deleted` webhook with `current_period_end = (today + 30 days).timestamp()`.
    - Assert tier IS STILL `clinic_standard` (paid period not over), `subscription_status="canceled"`, `current_period_end` stored.
    - Advance the clock to `today + 31 days`; call `revert_expired_canceled_orgs()` directly (NOT via scheduler — schedulers off in test env).
    - Assert tier is NOW `enterprise`, `billing.previous_tier == "clinic_standard"`, `billing.reverted_at` set.
    - Run `revert_expired_canceled_orgs()` a second time; assert idempotent (already-reverted org not touched again, return value 0).
9. `tests/billing/test_webhook_unsigned_in_prod.py`:
   - Use `monkeypatch.setenv("APP_ENV", "production")` + `monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)`.
   - POST any body → 400. Verifies the production fail-closed branch in `_is_production_env()` (which reads `os.environ` directly, so env monkeypatch is sufficient).
   - **Caveat documented in test docstring:** any `settings.APP_ENV`-gated branch elsewhere may be cached via Pydantic `Settings` and require `Settings.cache_clear()` to flip. Today only `_is_production_env()` is exercisable this way; future code that gates on `settings.APP_ENV` must add explicit cache invalidation in tests.

### Verification
```
pytest tests/billing -v
pytest --cov=policy_engine.billing --cov=policy_engine.routes.billing.clinic --cov-report=term-missing
```

### Exit criteria
- All Stripe SDK calls mocked — zero network requests during pytest run (verify with `respx.mock.assert_all_called()` or by checking `--collect-only` for any real httpx clients).
- Coverage ≥ 80 % on `billing/`, `routes/billing/clinic.py`.
- Production fail-closed branch covered.

### Commit
```
test(billing): Stripe webhook signature, idempotency, PII redaction

- Sign every webhook fixture; assert 400 on tamper/missing
- Per-handler payload assertions (checkout, sub, invoice)
- Production fail-closed when STRIPE_WEBHOOK_SECRET unset
- Customer Portal 409/200 paths with mocked Stripe SDK
```

---

## Phase 4 — SDK harness + synthetic clinic-admin AI agent

**Branch:** `tests/phase-4-sdk-agent`
**Depends on:** Phase 1
**Parallelizable:** with Phase 2, 3, 6
**Model tier:** strongest for agent design (Opus); default for SDK adapters
**Estimated tool calls:** 60–90

### Context brief
Three SDK surfaces in scope:
1. **Internal Sentinel SDK** — already has tests under `tests/sdk/`. Extend with clinic-tier-specific adapter tests (the `tests/sdk/test_llm_adapters.py` pattern).
2. **Anthropic Messages API** — wherever `policy_engine` calls Anthropic (search by `from anthropic` and `client.messages`). Mock with `respx` (httpx mock) — DO NOT use VCR because we cannot guarantee no PHI leaks into recorded cassettes.
3. **Synthetic clinic-admin agent (deterministic state machine — NOT `claude-agent-sdk`)** — a hand-rolled Python class that drives the FastAPI `client` through a scripted scenario. Covers the same *behavioral* surface as a real agent (multi-step user simulator) WITHOUT introducing a transitive dep that requires real Anthropic creds and is non-trivially mockable. **Rationale (review C2):** if we depended on `claude-agent-sdk` with `@pytest.mark.skipif`, CI would silently skip the synthetic-agent acceptance criterion; that violates the user's "thoroughly tested" requirement. A deterministic state machine is fully exercisable in CI and yields the same coverage of the API surface.

### Tasks
1. **Anthropic adapter tests** — `tests/sdk_harness/test_anthropic_messages.py`:
   - Use `respx` to intercept `https://api.anthropic.com/v1/messages`.
   - Test each call site in `policy_engine/` that uses `anthropic`.
   - Assert request shape (model, max_tokens, system prompt does NOT contain PHI patterns).
   - Test retry/backoff path on 429.
2. **Internal SDK clinic adapter** — extend `tests/sdk/`:
   - `tests/sdk/test_clinic_adapter.py` — clinic-tier-specific adapter glue.
3. **Stripe SDK** — already covered in Phase 3.
4. **Synthetic clinic-admin agent (state machine)** — `tests/agent/test_clinic_admin_agent.py`:
   - Define a `ClinicAdminScenario` dataclass: `name: str`, `steps: list[ScenarioStep]`, where each step has `intent`, `tool: Callable[[TestClient, dict], httpx.Response]`, `expected_status: int`, `assertions: Callable[[httpx.Response, Session], None]`.
   - Build a `ClinicAdminAgent(client: TestClient, db: Session)` class with pure-Python methods that map intents to API calls:
     - `onboard_clinic(name, tier, contact_email)` → POST `/v1/clinic/onboarding`
     - `register_tool(name, vendor, category, notes=None)` → POST `/v1/clinic/tools`
     - `sign_baa()` → POST `/v1/clinic/baa/sign`
     - `upload_observation(host, fingerprint)` → POST `/v1/clinic/shadow-ai/observations` (with extension token)
     - `generate_report()` → POST `/v1/clinic/reports`
     - `view_billing()` → GET `/v1/billing/clinic/plans`
   - The agent runs the scenario steps in order; for each step it calls the tool, asserts status, runs custom assertions, and accumulates a transcript. The transcript is asserted to contain ZERO PHI (independent presidio scan + `phi_text_check.scan_for_phi`).
   - Run scenarios:
     - **happy_path:** onboard → sign BAA → register 3 tools → upload obs → generate report → view billing
     - **phi_blocked:** try to register a tool with `notes` containing a fake SSN → assert 422 with `error="phi_in_freetext"` AND error message does NOT echo the SSN substring
     - **tier_block:** enterprise-tier user attempts clinic onboarding → 403
     - **cap_breach:** clinic_basic org tries to register 11 tools → 11th request 422 or 409 (per route spec; the test assertion accepts either; the route's actual code dictates which)
     - **baa_required:** clinic-with-no-BAA tries to register a tool that flips `handles_phi=True` → 403 with `error="baa_required"`
   - Assertions: scenario completes; `BillingEvent`, `ClinicAiTool`, `ClinicAiObservation`, `ClinicReportArtifact` rows present where expected; transcript scan returns zero PHI findings from BOTH scanners.
   - **No `claude-agent-sdk` dependency**, no skipif. Runs natively in CI.
5. **Determinism guards:** all LLM calls are stubbed; `respx` `assert_all_mocked` is enabled; CI fails if any test makes a real network call.

### Verification
```
pytest tests/sdk_harness tests/agent -v
pytest tests/agent --markers agent
```

### Exit criteria
- All scenarios complete end-to-end against in-memory test app.
- Zero network calls (respx asserts).
- No PHI in agent transcripts or DB (verified by both scanners).
- All scenarios run natively in CI — no skipif, no optional dep.

### Commit
```
test(sdk,agent): SDK harness + deterministic synthetic clinic-admin agent

- Anthropic adapter tests via respx (no real network)
- Hand-rolled state-machine agent runs onboard→BAA→tools→obs→report scenarios
- PHI guards on every assertion path (presidio + phi_text_check)
- No claude-agent-sdk dep; full coverage in every CI run
```

---

## Phase 5 — Frontend component + Playwright E2E

**Branch:** `tests/phase-5-ui-e2e`
**Depends on:** Phase 1 (env), Phase 2 (backend stable)
**Model tier:** default (Sonnet)
**Estimated tool calls:** 50–80

### Context brief
`dashboard/` already has `vitest`, `@testing-library/react`, and `@playwright/test` in devDependencies but no `tests/` folder and no `playwright.config.ts`. Build the component test layer first (vitest), then the E2E layer (Playwright with Page Object Model). The dashboard talks to the FastAPI backend — for E2E we need the backend running.

**E2E backend topology (corrected — review C3, C4):**
- Unit/integration tests use `sqlite:///:memory:` + `StaticPool` (single shared connection). This is incompatible with a separate `uvicorn` child process — `:memory:` is per-process. Multiple workers + StaticPool would also serialize.
- E2E uses **`sqlite:///./test_e2e_${RUN_ID}.db`** (file-backed, per-test-run RUN_ID UUID, gitignored, NullPool). The uvicorn child process AND the seed step share this file.
- Seeding: a Python script `dashboard/tests/e2e/seed.py` imports `tests.factories.clinic` directly (NOT via an HTTP route), connects to the same file-backed DB via SQLAlchemy, and writes the clinic org. Playwright's `globalSetup` runs this script via `child_process.execFileSync('python', ['tests/e2e/seed.py', '--db-url', dbUrl])`.
- **No `/v1/test/seed` route is added.** Adding it created an attack-surface risk in any environment with a misconfigured `APP_ENV` (review C3).
- Backend uvicorn startup cost is bounded — if > 5s on the dev box, fall back to MSW for E2E (the journeys then run against mocked APIs, with one final smoke-test that exercises the real backend end-to-end). MSW fallback is a separate decision documented when triggered.

### Tasks
1. **Vitest component tests** under `dashboard/src/pages/clinic/__tests__/`:
   - One `*.test.tsx` per clinic page (11 pages).
   - Mock `axios` / `react-query` calls with MSW handlers that return PHI-safe synthetic data.
   - Snapshot tests for visual stability (use `@testing-library/jest-dom` matchers, NOT image snapshots).
   - i18n: assert dictionary lookups under `dashboard/src/i18n/`.
2. **Playwright config** — `dashboard/playwright.config.ts`:
   - `testDir: "./tests/e2e"`.
   - `webServer: { command: "vite preview --port 0", port: <dynamic — read from stderr or use playwright's reusedExistingServer>}`. Hard-coding port 4173 collides with local dev.
   - `use: { baseURL, trace: "retain-on-failure", video: "retain-on-failure" }`.
   - **`retries: 0`** — no flaky-test masking. A failure is a failure.
   - Browsers: chromium only for v1 (firefox/webkit follow-up).
   - `globalSetup` boots backend uvicorn + runs `seed.py` against the file-backed sqlite. `globalTeardown` shuts down uvicorn and deletes the test DB file.
3. **Page Object Model** — `dashboard/tests/e2e/pages/`:
   - `OnboardingPage`, `BAAPage`, `ToolsPage`, `AlertsPage`, `ReportsPage`, `BillingPage`.
4. **E2E journey** — `dashboard/tests/e2e/clinic-happy-path.spec.ts`:
   - sign up → onboard → sign BAA → register tool with PHI-safe notes → upload observation → resolve alert → generate report → view billing
   - Capture trace + video on failure (already in config).
5. **Negative E2E tests** — `dashboard/tests/e2e/clinic-phi-blocked.spec.ts`:
   - Try to register a tool with a fake SSN in notes → assert 422 banner appears, error message NEVER includes the matched SSN string.
   - Screenshot the error state and assert the screenshot file does not contain PHI (text-extract via Playwright `page.locator` snapshot).
6. **Backend startup + seeding:**
   - `dashboard/tests/e2e/global-setup.ts` generates `RUN_ID = crypto.randomUUID()`, sets `DATABASE_URL=sqlite:///./test_e2e_${RUN_ID}.db`, boots FastAPI uvicorn as a detached child process, waits for `/health` 200, then runs `python dashboard/tests/e2e/seed.py --db-url sqlite:///./test_e2e_${RUN_ID}.db`.
   - `dashboard/tests/e2e/seed.py` imports `tests.factories.clinic` directly and writes a clinic_standard org with BAA signed plus a clinic admin user. Returns the JWT for that admin via stdout for Playwright to capture.
   - `dashboard/tests/e2e/global-teardown.ts` SIGKILLs uvicorn and deletes the DB file.
7. **No test-seed route in production code.** All seeding flows through the direct-import path above. This eliminates the `APP_ENV=="testing"` attack surface.

### Verification
```
cd dashboard && npm run test         # vitest
cd dashboard && npx playwright test  # E2E
```

### Exit criteria
- Vitest coverage ≥ 80 % on clinic pages.
- All E2E specs green on chromium with `retries: 0`.
- No PHI in screenshots, traces, or videos (verified by extracting text from each artifact and running BOTH `phi_text_check.scan_for_phi` AND a presidio scan; the test fails if either flags).
- No `/v1/test/seed` (or similar) route exists in `policy_engine/routes/` (assert via grep in CI).

### Commit
```
test(ui): vitest clinic page coverage + Playwright E2E happy path

- 11 vitest specs with MSW handlers (PHI-safe synthetic data)
- Playwright POM under tests/e2e/pages/
- Golden journey: onboard→BAA→tool→obs→report→billing
- PHI-blocked negative path with screenshot scrubbing
- Gated /v1/test/seed route (APP_ENV=testing only)
```

---

## Phase 6 — Extension smoke + full regression sweep

**Branch:** `tests/phase-6-regression`
**Depends on:** Phase 1
**Parallelizable:** with Phase 2, 3, 4
**Estimated tool calls:** 30–50

### Context brief
`clinic-extension/` is currently a vanilla MV3 extension with `manifest.json`, `background.js`, `options.js` — no build step, no tests. We add a smoke harness that loads the extension via Playwright's `launchPersistentContext` (chromium-only) and asserts it boots, the options page renders, and the background script registers expected listeners. Concurrent: a `regression` marker run that re-executes the full existing pytest suite (phase0–phase7) against the test DB to confirm we didn't regress anything.

### Tasks
1. `clinic-extension/tests/test_manifest.py` — Python test (because it's data, not code):
   - Load `manifest.json`; assert `manifest_version == 3`, `name`, `permissions` whitelist (no `<all_urls>`), `host_permissions` scoped, `content_security_policy` present.
2. `dashboard/tests/e2e/extension-smoke.spec.ts` — Playwright with `launchPersistentContext`:
   - Load extension; open the options page; assert title and form fields.
   - Send a fake DNS observation through the background script's message handler; assert it would POST to `/v1/clinic/shadow_ai/observations` (mocked).
3. **Regression marker (no aggregator file):** apply `@pytest.mark.regression` to existing `tests/test_phase[0-7]_*.py` test functions (top-of-file `pytestmark = pytest.mark.regression`). CI runs `pytest -m regression` natively. **Do NOT** create a `test_regression_sweep.py` that re-runs other tests — pytest-inside-pytest breaks fixture isolation (review M6).
4. `pyproject.toml` — confirm `regression` marker registered (Phase 1 added it).

### Verification
```
pytest -m regression
cd dashboard && npx playwright test extension-smoke
```

### Exit criteria
- Extension boots in chromium; options page loads.
- Manifest validation green (no overly-broad permissions).
- Full regression sweep green — phase0..phase7 + new clinic tests all pass together.

### Commit
```
test(extension,regression): extension smoke + full regression sweep

- Playwright launchPersistentContext extension test
- Manifest v3 hygiene assertions
- @pytest.mark.regression aggregator over phase0..phase7
```

---

## Phase 7 — CI, coverage gate, compliance audit

**Branch:** `tests/phase-7-ci-audit`
**Depends on:** ALL prior phases
**Model tier:** default (Sonnet)
**Estimated tool calls:** 30–50

### Context brief
Final gate. Wire everything into GitHub Actions, enforce the coverage threshold, run a security scan, and ship `TEST_PLAN.md` and a coverage report. This phase is where the acceptance criteria are mechanically enforced.

### Tasks
1. `.github/workflows/test.yml`:
   - Matrix: `python-version: [3.11, 3.12]`, `node-version: [20]`.
   - Jobs: `lint` (ruff + eslint), `pytest` (coverage XML), `vitest` (coverage), `playwright` (artifacts upload), `bandit` (security scan), `phi-scan` (custom step).
   - Use `actions/upload-artifact@v4` for traces + videos + coverage XML.
2. **Per-file coverage gate via `diff-cover`:**
   - `pytest-cov` cannot enforce per-file thresholds — `--cov-fail-under` is a single global threshold (review H5). Use `diff-cover` (PyPI: `diff_cover`) which is built for "coverage on changed lines vs. base ref".
   - Step: `pytest --cov=policy_engine --cov-report=xml:coverage.xml`, then `diff-cover coverage.xml --compare-branch=07572e9 --fail-under=80`.
   - Output is per-file delta with line-level highlighting; fails the build if any changed line falls below 80%.
3. **Independent PHI meta-scan** — `tests/test_phi_scan_meta.py` (review H3 — phi_text_check IS the SUT, so cannot self-validate):
   - Run **`presidio-analyzer`** (independent detector; covers names, addresses, MRN-shaped IDs, FHIR resource IDs that `phi_text_check._PATTERNS` does NOT cover) over every fixture file, every factory output, every recorded HTTP response in tests, and every Playwright screenshot's extracted text.
   - Assert `presidio.analyze(text)` returns no findings above confidence 0.5.
   - Compare deltas: fixtures that `phi_text_check` clears but presidio flags become detector-gap tickets (filed but NOT fixture-blocking — they are signals to harden the production detector).
   - Test fails if presidio finds any PHI in fixtures.
4. `bandit -r policy_engine/billing policy_engine/routes/clinic policy_engine/services/clinic_*.py policy_engine/services/phi_text_check.py` — must report 0 HIGH and 0 MEDIUM (the `B` codes for SQL/secrets/exec).
5. `TEST_PLAN.md` — final document at repo root referencing every phase; lists acceptance criteria + how each was verified.
6. **Security review:** spawn the `security-reviewer` agent against the diff between `07572e9` and HEAD + all new test code. Capture output as `docs/SECURITY_REVIEW_CLINIC_TESTS.md`. Block on any CRITICAL/HIGH.
7. **HIPAA/GDPR audit:** invoke the `healthcare-phi-compliance` skill; capture output as `docs/COMPLIANCE_REVIEW_CLINIC_TESTS.md`.
8. Update `MEMORY.md`: add a feedback memory if the project picks up a non-obvious convention (e.g., "all new test fixtures must be PHI-safe per Phase 1 factory module").

### Verification
```
.github/workflows/test.yml — green on a manual workflow_dispatch
pytest --cov-fail-under=80 --cov=<changed files>
bandit -r <clinic surface> — exits 0 HIGH/MEDIUM
```

### Exit criteria
- CI green on PR.
- Coverage ≥ 80 % on every file changed since `07572e9`.
- Security scan: 0 CRITICAL / 0 HIGH.
- Compliance audit: passing or all findings closed.
- `TEST_PLAN.md` checked in at repo root.

### Commit
```
ci(tests): enforce coverage gate, security + PHI compliance scans

- GH Actions matrix: pytest + vitest + Playwright + bandit
- 80% coverage gate scoped to files changed since 07572e9
- PHI meta-scan over all fixtures
- TEST_PLAN.md + security/compliance review docs
```

---

## Anti-pattern catalog (review checklist for every phase)

- [ ] No real PHI in fixtures, factories, snapshots, or recorded responses.
- [ ] No real network calls (`respx.assert_all_mocked` enabled; CI sets `--block-network`).
- [ ] No `print()` statements; use `logging`.
- [ ] No `time.sleep()` for synchronization — use `pytest-asyncio` or explicit waits.
- [ ] No mutation of `Base.metadata` outside conftest.
- [ ] No skipped tests without a tracked TODO and a GitHub issue link.
- [ ] No hardcoded JWTs / API keys / Stripe secrets — use fixtures + `.env.test`.
- [ ] No `@pytest.mark.xfail` without a why-comment + ticket.
- [ ] No raw SQL in tests — use SQLAlchemy session.
- [ ] Tests do not write to `policy_engine/` source.
- [ ] No `datetime.now()` / `datetime.utcnow()` in tests without `freezegun.freeze_time` — clock-sensitive code must run on a frozen clock.
- [ ] Tier-gating tests cover every clinic route (no "tested in another file" hand-waves).
- [ ] PHI-blocked tests assert error messages do NOT echo the matched text.
- [ ] No flaky-test retries (`Playwright retries: 0`, `pytest --no-flaky`). A failure is a failure.
- [ ] No pytest-inside-pytest aggregators — use markers.
- [ ] No new HTTP routes that exist only for tests (e.g., `/v1/test/seed`) — seed via direct factory imports.
- [ ] No optional `claude-agent-sdk`-style deps for *acceptance-criteria* test code — fully covered must mean fully covered in CI.
- [ ] `pytest-randomly` enabled — tests must be order-independent.
- [ ] Two PHI scanners (presidio + `phi_text_check`) run on every fixture; circular self-validation is forbidden.

## Plan mutation protocol

If a phase reveals a real bug in the production code:
1. STOP — do not paper over with test changes.
2. Open a `bug/` branch off `main` (NOT off the test branch), fix the bug, PR, merge.
3. Resume the test phase with the updated `main` rebased in.

If a phase grows beyond ~120 tool calls:
1. Split into `phase-N-a`, `phase-N-b` with new dependency edges.
2. Update this plan file via PR before continuing.

If `claude-agent-sdk` cannot be installed in CI:
1. Mark the synthetic-agent scenarios `@pytest.mark.skipif`.
2. Open a follow-up issue to host the agent harness in a separate Docker image.

---

## Acceptance summary

| Criterion | Verified by |
|---|---|
| All journeys pass | Phase 5 + Phase 6 sweep |
| ≥ 80 % coverage on changed files | Phase 7 CI gate |
| 0 CRITICAL/HIGH from `security-reviewer` | Phase 7 step 6 |
| `healthcare-phi-compliance` clean | Phase 7 step 7 |
| Playwright artifacts uploaded; no quarantines | Phase 5 + CI |
| Atomic per-phase commits | This plan, one PR per phase |
| No PHI anywhere | PHI-meta scan (Phase 7 step 3) + factory contract (Phase 1) |
