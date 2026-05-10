# TEST_PLAN — Sentinel AI / Devotrex

This is the live test-plan index. Each phase below maps to a section in
[`plans/clinic-tier-test-suite.md`](plans/clinic-tier-test-suite.md) and
populates as work lands.

## Acceptance criteria (replace "zero errors and bugs")

- [ ] All defined journeys pass on a clean checkout.
- [ ] pytest coverage ≥ 80% on files changed since `07572e9` (gated via `diff-cover`).
- [ ] `security-reviewer` returns 0 CRITICAL / 0 HIGH on the test diff.
- [ ] `healthcare-phi-compliance` skill scan passes.
- [ ] Two PHI scanners (`phi_text_check` + `presidio-analyzer`) report no findings on any fixture, factory output, or recorded test artifact.
- [ ] Playwright artifacts uploaded; no quarantined or `.skip`'d tests without an issue link.
- [ ] Each phase committed atomically with a conventional-commit message.
- [ ] No new HTTP routes exist solely for testing (e.g., `/v1/test/seed`).
- [ ] Clinic routes are JWT-only — API-key access returns 401.

## Phase status

| # | Phase | Status | Tests | Commit |
|---|---|---|---|---|
| 0 | Blueprint plan committed | ✅ done | — | `docs(plan): blueprint for clinic-tier test suite` |
| 1 | Foundation & fixtures | ✅ done | 8 smoke | `test(infra): scaffold clinic-tier test foundation` |
| 2 | Backend unit + integration (clinic) | ✅ done | 137 | `test(clinic): unit + integration tests` |
| 3 | Billing + Stripe webhook | ✅ done | 41 | `test(billing): Stripe webhook signature, idempotency, PII redaction` |
| 4 | SDK harness + synthetic agent | ⏳ pending | — | — |
| 5 | Frontend + Playwright E2E | ⏳ pending | — | — |
| 6 | Extension smoke + regression sweep | ⏳ pending | — | — |
| 7 | CI, coverage gate, compliance audit | ⏳ pending | — | — |

## Production bugs surfaced by the test suite

| ID | Severity | File | Status |
|---|---|---|---|
| P-BUG-1 | HIGH | `policy_engine/main.py` lifespan re-registers scheduler jobs unconditionally; `scheduler.register()` raises on duplicate. Crashes on graceful redeploy / hot reload / pytest TestClient re-entry. | Worked around in `.env.test`; **prod fix pending** |
| P-BUG-2 | MEDIUM | `tests/test_phase0_security.py::TestCSRFProtection::test_post_without_csrf_token_returns_403_for_jwt_auth` failing on the current working tree. Pre-existing, likely tied to recent `routes/auth.py` edits. | **Pre-existing; out of scope** |
| P-BUG-3 | CRITICAL | `policy_engine/middleware/csrf.py` did not exempt the Stripe webhook path. Stripe servers cannot send CSRF tokens, so every webhook returned 403 in production — billing was silently broken. | ✅ **Fixed** in `fix(security): exempt /v1/billing/clinic/webhook from CSRF middleware` |
| Factory | LOW | Existing `tests/conftest.py::admin_user_jwt` fixture uses `"sub"` payload key; production `routes/auth.py:105` and `get_current_user` use `"user_id"`. The fixture is silently broken (any test using it against a real route returns 401). My factories use `"user_id"` to match production. | **Surfaced; not fixed** |

## Phase 1-3 deferrals (track as Phase 7 follow-up issues)

- `test_routes_settings.py`, `test_routes_policy_templates.py`, `test_routes_alerts.py`, `test_routes_dashboard.py`, `test_routes_shadow_ai.py`, `test_routes_reports.py` — placeholder `__init__.py` only
- `test_clinic_pdf_report.py` — needs WeasyPrint optional dep + pdfplumber-based PDF text scrubbing
- Migration tests — needs testcontainers-postgres in CI
- Phases 4-7 entirely

## How to run

```bash
# Backend unit + integration
pytest tests/services_clinic tests/clinic -v

# Billing
pytest tests/billing -v

# SDK + synthetic agent
pytest tests/sdk_harness tests/agent -v

# Full regression
pytest -m regression

# Coverage report (per-file gate via diff-cover)
pytest --cov=policy_engine --cov-report=xml:coverage.xml
diff-cover coverage.xml --compare-branch=07572e9 --fail-under=80
```

## Known constraints

- E2E tests require Docker (Postgres testcontainer for migration tests; uvicorn child process for Playwright).
- `claude-agent-sdk` is **not** a dependency; the synthetic agent is a deterministic state machine.
- Stripe tests use signed local fixtures — no real Stripe sandbox.
