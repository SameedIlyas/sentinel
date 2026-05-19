# Sentinel AI — Production Readiness Assessment

> **Date of assessment:** 2026-05-19
> **Branch reviewed:** `feat/clinical-shield-v1` (HEAD `14daf6f`)
> **Scope:** can this codebase be deployed and used "without any caveat"?
> **Authoritative source for findings:** `REVIEW.md` (consolidated audit, dated 2026-05-16 → 2026-05-17), plus `PR_BODY.md` (remediation pass 1) and `plans/clinical-shield-v1.md` (post-fix mutation log).

---

## Verdict

**NO — the codebase is NOT ready for unconditional production deployment.**

The platform is a healthcare-adjacent AI governance system. A formal six-agent
read-only audit on `main` (commit `3ae3f7c`, 2026-05-16) returned a hard
**BLOCK** verdict with **13 CRITICAL + 31 HIGH + 24 MEDIUM + 15 LOW = 83
findings**.

Since that audit:

- **Pass 1 (`fix/security-and-logic-pass-1`, merged as PR #1)** closed **10 of
  31 HIGH** findings.
- **The Tier-A v1.0 workstream** (commits since PR #1 to HEAD) landed feature
  work (R2 product-role projection, A1 model-training-status registry) plus
  six review fixes scoped to *those features*. It did **not** touch the
  deferred CRITICAL list.
- **All 13 CRITICAL** findings remain open. **21 of 31 HIGH** remain open.
  **24 MEDIUM** and **15 LOW** remain unaddressed.

The plan-mutation log records this plainly:

> "the 13 deferred CRITICALs are now part of main as deferred items, **not
> fixed**."
> — `plans/clinical-shield-v1.md`, mutation log entry 2026-05-17

The platform can be safely deployed to a **controlled, single-tenant, internal
network for evaluation or pilot** with the caveats documented below. It
**cannot** be deployed to a HIPAA-covered entity, to any context where two or
more orgs share the instance, or to any internet-exposed production
environment, until the CRITICAL cluster is closed.

---

## Triage snapshot (current)

| Severity | Found in audit | Closed | Open |
|---|---:|---:|---:|
| CRITICAL | 13 | 0 | **13** |
| HIGH | 31 | 10 | **21** |
| MEDIUM | 24 | 0 | **24** |
| LOW | 15 | 0 | **15** |
| **Total** | **83** | **10** | **73** |

Coverage from the full pytest run: **76 %** (1166 passed / 13 failed / 3
skipped). The `rules/common/testing.md` 80 % floor is **not** met. The 13
failures are pre-existing and gated on missing dev deps (`stripe`,
`freezegun`).

---

## The 13 open CRITICALs — what each blocks

Each finding below is sourced from `REVIEW.md`. The "blocks" column states
which deployment shape the finding makes unsafe.

| ID | Category | Defect (one-line) | Blocks |
|---|---|---|---|
| **CRIT-001** | tenancy | `/v1/audit/logs`, `/v1/agents`, `/v1/policies`, `/v1/alerts` list any tenant's rows to any authenticated user | **Multi-tenant**, **HIPAA** |
| **CRIT-002** | audit-chain | HITL hash chain is recomputed on every append — verifies a forged history as valid | **HIPAA**, **21 CFR Part 11** |
| **CRIT-003** | audit-chain | HITL chain verification always returns `False` (tz-format mismatch) — control is non-operational | **HIPAA** |
| **CRIT-004** | tenancy | `/v1/clinical/hitl/*` has no tenant filter on read or write — any user can approve another clinic's reviews | **Multi-tenant**, **HIPAA** |
| **CRIT-005** | audit-chain | Prior-auth chain cannot detect tail deletion; no `seq_no`, no monotonicity check | **HIPAA**, **CMS-0057-F** |
| **CRIT-006** | billing | Stripe `customer.subscription.updated` never writes `org.tier` — paid downgrades / portal-created subs grant unlimited tier | **Any deployment using billing** |
| **CRIT-007** | auth | JWT blacklist not checked in `authenticate_request` — logout doesn't invalidate tokens for audit/agents/alerts/policies routes for 24 h | **All deployments** |
| **CRIT-008** | retention | Audit retention `DELETE`s without legal-hold check or archive-durability confirmation; 365-day hard delete violates HIPAA 6-year retention floor | **HIPAA** |
| **CRIT-009** | migration | PostgreSQL `userrole` enum still has only `ADMIN`/`ANALYST`/`VIEWER`; 8 healthcare roles cannot be persisted on Postgres | **All Postgres deployments using healthcare roles** |
| **CRIT-010** | tenancy / data integrity | `organization_id` is `nullable=True` on every multi-tenant table — NULL rows leak across orgs | **Multi-tenant**, **HIPAA** |
| **CRIT-011** | auth / XSS | JWT + serialised `User` object live in `localStorage`; XSS exfiltrates both, and forged role/tier passes every client-side check | **All deployments** |
| **CRIT-012** | rbac | `/clinic/*` dashboard routes have no tier guard at the routing layer — any authenticated user can render BAA forms, compliance pages, etc. by typing the URL | **Multi-tier deployments** |
| **CRIT-013** | auth | JWT sent as `?token=<JWT>` on every WebSocket open — lands in access logs, CDN logs, proxy logs, browser history | **All deployments** |

The cluster is concentrated in three areas:

1. **Tenancy is not enforced** at the database, ORM, or several route layers
   (CRIT-001, -004, -010, plus much of the HIGH list). Single-tenant
   deployments dodge this; anything multi-tenant does not.
2. **Audit chains do not provide tamper evidence** (CRIT-002, -003, -005,
   -008). This is the contract Sentinel sells. The current implementations
   either always pass (recompute), always fail (tz mismatch), or cannot
   detect tail deletion.
3. **Auth has live exfiltration paths** (CRIT-007, -011, -013). Stolen tokens
   are usable for the full TTL even after logout; localStorage gives any XSS
   a working bearer token; the WS query-string spreads it to logs.

---

## What works well

To be balanced — the platform is far from greenfield. It has been built with
care in several places and the audit highlights this:

- **Domain coverage is broad and coherent.** FHIR, DICOM, model-card auto-fill
  (GitHub + MLflow), bias audits, HITL workflow, PMS reports, technical files,
  risk scoring, drift, prior-auth, revenue cycle, clinic-tier UX, browser
  extension. The route map (`policy_engine/main.py:215-255`) is wide and
  consistent.
- **Startup guards are enforced in production**: SECRET_KEY strength, weak-key
  blocklist, CORS wildcard refusal under `APP_ENV=production`. Smoke-tested
  (`tests/test_startup_guards_smoke.py`).
- **PHI redaction runs on audit-log writes** (`policy_engine/services/phi_text_check.py`).
- **SSRF protection** on outbound URL fetches with a thorough IPv6 blocklist
  (HIGH-032 closed).
- **Rate limiting + CSRF + tenant context middleware** are wired in
  `policy_engine/main.py:198-202`.
- **Migrations** are alembic-managed (18 revisions), with at least one
  reversibility fix (HIGH-014).
- **Tests:** 1166 pass; 76 % coverage on a 11.7 k-statement codebase; CI
  enforces PHI meta-scan + extension manifest hygiene + bandit.
- **Containerised cleanly** — non-root user in both backend and frontend
  images, multi-stage builds, health-checks, no secrets in the image.
- **Observability and ops hooks** are reasonable: `/health`, structured
  logging, in-process asyncio scheduler with idempotency.

This is a system whose blockers are well-known and largely concentrated —
not a system whose foundation is shaky. The CRITICAL list is plainly
addressable; it just has not been addressed yet.

---

## Deployment shapes — what each can and cannot safely do

| Shape | Internal eval / pilot, 1 org, no PHI | Internal prod, 1 org, no PHI | Multi-tenant SaaS | HIPAA-covered entity |
|---|:---:|:---:|:---:|:---:|
| Demo box (single VM) | ✅ | ⚠️ (with §10 checklist + caveats below) | ❌ | ❌ |
| Reverse-proxied prod | ✅ | ⚠️ | ❌ | ❌ |
| Kubernetes / Helm | ✅ | ⚠️ | ❌ | ❌ |

- **✅ Internal eval / pilot, 1 org, no PHI** — safe today. CRITICAL impact
  is limited because (a) only one tenant exists, so the cross-tenant leak is
  mooted; (b) no PHI means HIPAA/§164.312 clauses do not bind; (c) audit
  chain quality is a posture concern, not a regulator concern.
- **⚠️ Internal prod, 1 org, no PHI** — possible, but you are accepting
  CRIT-007 (logout doesn't kick the token from audit/agents/alerts/policies
  routes), CRIT-011 (localStorage JWT), CRIT-013 (JWT in WS URL → server
  logs). If your threat model says "internal users on a trusted network with
  TLS and no XSS-prone third-party content," these are mitigable but not
  zero.
- **❌ Multi-tenant SaaS** — blocked by CRIT-001, CRIT-004, CRIT-010 (tenancy
  is structurally not enforced). Do not run.
- **❌ HIPAA-covered entity** — blocked by CRIT-002, CRIT-003, CRIT-005 (audit
  controls), CRIT-008 (retention floor), CRIT-009 (healthcare role enum gap
  on Postgres), plus everything above. Do not run.

---

## Test status caveats

- **Coverage 76 %** — below the 80 % floor in `rules/common/testing.md`.
- **13 pre-existing test failures** gated on missing dev deps (`stripe`,
  `freezegun`). These are infra issues, not regressions, but they mean the
  full billing path is not exercised by CI.
- **No Playwright E2E suite is wired up.** `@playwright/test` is a devDep
  but `playwright.config.*` and an `e2e/` directory are absent.
- **One snapshot-guard test** (`tests/test_r2_no_backend_change.py`) was
  CRLF-sensitive in the recent R2 merge and required a follow-up commit
  (`13d1028`). The maintainer note is documented; future changes to
  `policy_engine/models/user.py` will trip the guard until the SHA is
  re-captured with `git cat-file blob HEAD:path | sha256sum`.

---

## Recommended remediation order before "deploy anywhere"

If the goal is to remove the unconditional caveats, the minimum closing
sequence is:

1. **Auth blacklist + token surface** — CRIT-007, CRIT-011, CRIT-013, plus
   HIGH items HIGH-024 / HIGH-030 paired with them. Self-contained
   (`policy_engine/auth/rbac.py`, `dashboard/src/api/client.ts`, WS handshake
   in `routes/websocket.py`). Probably 2–4 engineer-days.
2. **Tenancy enforcement at the read paths** — CRIT-001, CRIT-004. Add
   `.filter(Model.organization_id == current_user.organization_id)` to every
   listing route in `routes/audit.py`, `routes/agents.py`, `routes/policies.py`,
   `routes/alerts.py`, `routes/clinical/hitl.py`. Plus regression tests
   asserting 404 across orgs. 3–5 engineer-days for code; another 2 for
   tests.
3. **`organization_id NOT NULL` migration** — CRIT-010. Backfill survey, then
   `ALTER COLUMN ... SET NOT NULL` on each multi-tenant table. Use a
   defensive migration with NULL-count check before constraint add. 2–3
   engineer-days. PostgreSQL RLS is an ARCH-FOLLOWUP, not in this sequence.
4. **Healthcare role enum migration** — CRIT-009. New alembic revision with
   `ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'cmio';` … (outside a
   transaction, one statement per value). Reconcile the `ADMIN`/`ORG_ADMIN`
   alias collision. 1 engineer-day.
5. **Audit-chain redesign** — CRIT-002, CRIT-003, CRIT-005. This is the
   hardest cluster and the most regulator-facing. Append-only schema (insert
   only, never update) plus DB triggers preventing `UPDATE` on hash columns;
   monotonic `seq_no`; external anchor for tail-deletion detection. The plan
   already flags this as an `ARCH-FOLLOWUP`. Budget: 1–2 weeks if you take
   the time to do it right.
6. **Retention with legal-hold gate** — CRIT-008. Add `legal_hold` column,
   exclude from purge, real FK on `alerts.audit_log_id`, archive-durability
   ETag round-trip before delete. 3–4 engineer-days.
7. **Billing tier propagation** — CRIT-006. Inside `_handle_subscription_updated`,
   resolve tier from Stripe plan metadata and write `org.tier` when status is
   `active`/`trialing`. Plus a `TierStateMachine` (`ARCH-FOLLOWUP`) for the
   full state grid. 2–3 engineer-days for the immediate fix.
8. **Tier guards on `/clinic/*` routes** — CRIT-012. Extend `ProtectedRoute`
   with `requiredTiers`. 1–2 engineer-days plus server-side
   enforcement on the matching routes.

**Sequence rationale:** auth + tenancy first because they remove the largest
exposure to existing data; schema migrations second because they require
backfill windows; audit-chain last because it is the riskiest single
refactor and benefits from doing the others first so the test surface is
clean.

Total: roughly **3–5 weeks of focused engineering** to close the CRITICAL
cluster, assuming an experienced engineer/team and no scope creep into the
HIGH/MEDIUM list. The HIGH/MEDIUM list adds another 2–3 weeks of cleanup
before "no caveats" is honest.

---

## If you must deploy *today*

For an internal, single-tenant, non-PHI pilot the practical path is:

1. Follow `DEPLOYMENT.md` end-to-end. Walk the §10 checklist.
2. Restrict the deployment to a single Organization. Do not create a second
   one. (CRIT-001 / CRIT-004 / CRIT-010 lose teeth when there is only one
   tenant.)
3. Use **SQLite or PostgreSQL** with the awareness that healthcare roles
   beyond `ADMIN`/`ANALYST`/`VIEWER` will not work on Postgres until
   CRIT-009 is fixed. On SQLite (dev only) the enum constraint is not
   enforced and all roles are insertable.
4. Set `ACCESS_TOKEN_EXPIRE_MINUTES=120` (2 hours) to shrink the CRIT-007
   replay window.
5. Run behind a reverse proxy that **does not log full URLs**, or stripes
   query strings (mitigates the CRIT-013 token-in-URL footprint until the
   WS-ticket pattern lands).
6. Treat the audit trail as **best-effort**, not regulator-grade, until the
   chain rebuild lands (CRIT-002/003/005).
7. Do not enable the billing/Stripe flow unless you specifically need it and
   have read CRIT-006.
8. Do not exposed the platform to the public internet.
9. Read this document in full before signing the deployment off, and
   record in your change-management system that you have consciously
   accepted the open CRITICAL list.

---

## Bottom line

The honest answer to *"is this ready to be used and deployed without any
caveat?"* is **no**. The codebase is feature-complete, well-tested in many
places, and architecturally coherent — but it has 13 open CRITICAL findings
that the team itself has documented and deferred, and most of them are on the
exact surfaces (multi-tenancy, audit integrity, token handling) that "without
any caveat" implies.

It **is** ready for a **single-tenant, internal, non-PHI evaluation** if you
walk the §10 checklist in `DEPLOYMENT.md` and accept the caveats in §"If you
must deploy today" above. It **is not** ready for HIPAA, multi-tenant, or
internet-exposed production. The path from where it is today to "no caveats"
is real, scoped, and estimable — roughly 3–5 weeks of focused engineering to
close the CRITICAL cluster, another 2–3 weeks for the HIGH/MEDIUM tail.

*End of readiness assessment.*
