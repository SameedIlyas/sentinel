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

| # | Phase | Status | Branch / Commit |
|---|---|---|---|
| 0 | Blueprint plan committed | ✅ done | `docs(plan): blueprint for clinic-tier test suite` |
| 1 | Foundation & fixtures | 🟡 in progress | `test(infra): scaffold clinic-tier test foundation` |
| 2 | Backend unit + integration (clinic) | ⏳ pending | — |
| 3 | Billing + Stripe webhook | ⏳ pending | — |
| 4 | SDK harness + synthetic agent | ⏳ pending | — |
| 5 | Frontend + Playwright E2E | ⏳ pending | — |
| 6 | Extension smoke + regression sweep | ⏳ pending | — |
| 7 | CI, coverage gate, compliance audit | ⏳ pending | — |

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
