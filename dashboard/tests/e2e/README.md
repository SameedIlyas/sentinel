# Phase 5 — UI E2E (deferred)

This directory is reserved for Playwright E2E tests of the clinic dashboard.
The construction plan for it lives at
[`plans/clinic-tier-test-suite.md`](../../../plans/clinic-tier-test-suite.md)
under "Phase 5 — Frontend component + Playwright E2E".

## Status

⏳ **Deferred** to a separate session. The fixtures, factories, and
backend test infrastructure (Phases 1-4 + 6) are in place. A future
session can pick this up cold from the plan's per-phase context brief.

## Why deferred

The unit/integration suite uses `sqlite:///:memory:` + `StaticPool` (single
shared connection). E2E needs a real running uvicorn process, which has
its own memory space — `:memory:` is incompatible. The plan calls for
file-backed sqlite (`sqlite:///./test_e2e_${RUN_ID}.db`) + `NullPool` for
the uvicorn child process, with seeding via direct factory imports (not
an HTTP route — see Phase 5 review C3).

That topology is straightforward to build but needs a clean session to
do well; rushing it under a tool budget alongside Phases 1-4+6+7 risks
flake.

## What's already done that this phase can use

- `tests/factories/clinic.py` — PHI-safe org/admin/tool/observation factories
- `tests/factories/billing.py` — Stripe webhook signing helper
- `tests/clinic/test_routes_*.py` — Backend integration tests prove the
  API surface is stable
- `tests/agent/test_clinic_admin_agent.py` — Behavioral E2E coverage
  via deterministic state machine, no UI

## What still needs writing

Per Phase 5 of the plan:

1. `dashboard/playwright.config.ts` — `retries: 0`, dynamic port for vite preview
2. `dashboard/tests/e2e/global-setup.ts` — boot uvicorn + run `seed.py`
3. `dashboard/tests/e2e/seed.py` — Python script that imports
   `tests.factories.clinic` and writes to the file-backed DB; emits the
   admin JWT to stdout
4. `dashboard/tests/e2e/global-teardown.ts` — kill uvicorn, delete the DB file
5. `dashboard/tests/e2e/pages/` — Page Object Model for each clinic page
6. `dashboard/tests/e2e/clinic-happy-path.spec.ts` — onboard → BAA → tool
   → observation → resolve alert → report → billing
7. `dashboard/tests/e2e/clinic-phi-blocked.spec.ts` — PHI in tool notes →
   422 banner; assert error UI does NOT echo the matched substring;
   screenshot text-extracted and PHI-scanned
8. `dashboard/tests/e2e/extension-smoke.spec.ts` — `launchPersistentContext`
   loads `clinic-extension/` and exercises options page
9. `dashboard/src/pages/clinic/__tests__/*.test.tsx` — vitest component
   coverage with MSW handlers (PHI-safe synthetic data)
