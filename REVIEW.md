# Sentinel AI — Consolidated Audit Report

**Date:** 2026-05-16 → 2026-05-17
**Branch:** `main` @ commit `3ae3f7c`
**Method:** Read-only static analysis by six specialised audit agents (security, healthcare/PHI, python, typescript, database, business-logic).
**Source section files:** `REVIEW.security.md`, `REVIEW.healthcare.md`, `REVIEW.python.md`, `REVIEW.typescript.md`, `REVIEW.database.md`, `REVIEW.logic.md` — each block below is sourced from one of these and cross-referenced via the `Source` field.

> **Caveat on TypeScript coverage:** The TypeScript reviewer's `REVIEW.typescript.md` file was truncated after writing all 3 CRITICAL and 7 HIGH findings. Its counts table reports 5 MEDIUM and 3 LOW, but those finding bodies were never written. The triage table below reflects only what was actually written.

---

## Verdict

**BLOCK** — 13 CRITICAL findings, multiple of them stacking on the HIPAA audit-control contract (`§164.312(a)(1)`, `§164.312(b)`, `§164.312(c)(1)`) and the platform's tenant-isolation invariant. Cannot deploy to a covered entity in current state.

The deepest issues cluster in three areas: (a) **tenancy is non-existent at the database, ORM, and route layers** for several listing endpoints — any authenticated user can read any tenant's audit logs, alerts, agents, policies, HITL queues, and admin shadow-AI detections; (b) **the audit chains do not provide tamper evidence** — the HITL chain is recomputed on every append, the prior-auth chain cannot detect tail deletion, and one chain column has an empty-string default that lets the verifier validate falsified rows; (c) **the dashboard's tier and role gates are cosmetic** — `/clinic/*` routes have no server-enforced tier guard at the routing layer, and `/admin/*` routes have no role guard, so direct URL entry bypasses the sidebar filter.

---

## Triage Table — Severity × Surface

| Severity | policy_engine | dashboard | extension | sdk | cross | **Total** |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|
| CRITICAL | 10 | 3 | 0 | 0 | 0 | **13** |
| HIGH     | 23 | 7 | 1 | 0 | 0 | **31** |
| MEDIUM   | 24 | 0\* | 0\* | 0 | 0 | **24** |
| LOW      | 10 |  3 | 1 | 1 | 0 | **15** |
| **Total**| **67** | **13** | **2** | **1** | **0** | **83** |

\* TypeScript MED (5) and LOW (3) declared in source counts but agent output was truncated before writing them — not reflected here.

### Triage by Category (CRITICAL + HIGH only)

| Category | Count | Notes |
|---|---|---|
| tenancy (cross-tenant data leak) | 9 | Largest cluster — applies to audit, agents, policies, alerts, HITL, transparency, admin shadow-AI, redaction logs |
| audit-trail integrity | 6 | Includes HITL chain recompute, prior-auth tail deletion, empty-hash default, missing scheduled verifier, mutable `created_at` ordering, audit-log retention without legal-hold |
| auth | 5 | JWT in URL, JWT in localStorage, blacklist not checked, 24h non-rotating token, BAA self-acceptance |
| rbac | 3 | Missing route-level role/tier guards on dashboard |
| billing / state-machine | 4 | subscription_updated never writes tier; unpaid never reverts; email-fallback cross-tenant; Stripe table-scan |
| phi | 3 | `update_practice` no PHI scan; scribe-auditor embeds claim text; PHI patterns gaps |
| migration | 3 | Migration 006 no-op breaks roles; 005 missing index drops; 017 swallows backfill exceptions |
| schema / index | 4 | Composite index gaps on prior_auth, audit_logs, clinic_ai_tools; entry_hash default `''` |
| ssrf | 2 | IPv6 ULA missing; extension endpoint user-configurable |
| async | 1 | Sync `requests` blocks event loop |
| logic | 4 | Internal error echo to clients; bias-audit gate workaround missing; HITL SLA wall-clock only; model-card transitions missing |

---

## CRITICAL Findings

### policy_engine

#### CRIT-001 — Cross-tenant data leak across `/v1/audit/logs`, `/v1/agents`, `/v1/policies`, `/v1/alerts`
- **Source:** REVIEW.python.md (CRIT-001)
- **Category:** tenancy
- **file:line:** `policy_engine/routes/audit.py:130`, `policy_engine/routes/agents.py:52`, `policy_engine/routes/policies.py:278`, `policy_engine/routes/alerts.py` (equivalent pattern)
- **description:** Listing routes `db.query(<Model>)` without any `organization_id` filter. `TenantContextMiddleware` writes `org_id` into `request.state` but none of these routes read it. Any authenticated user — regardless of org — can enumerate every tenant's data.
- **exploit_path:** Attacker with any valid token calls `GET /v1/audit/logs?page_size=100` and receives PHI-adjacent audit records (tool arguments, data_touched, agent_id) from ALL orgs. Same for policies/agents/alerts. No prerequisite beyond a valid token.
- **recommended_fix:** Add `.filter(Model.organization_id == current_user.organization_id)` to every listing/detail query. Enable PostgreSQL RLS as defense-in-depth.
- **blast_radius:** touches enterprise
- **regulatory_touch:** HIPAA §164.312(a)(1), §164.312(b)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1)

#### CRIT-002 — HITL audit "hash chain" is recomputed and overwritten on every append
- **Source:** REVIEW.healthcare.md (CRIT-001) + REVIEW.logic.md (CRIT-002 defect A)
- **Category:** audit
- **file:line:** `policy_engine/routes/clinical/hitl.py:144-149`
- **description:** `_append_audit_entry` loads all existing rows, calls `build_audit_chain` over (old + new), then writes the new hashes back into prior DB rows. Equivalent to "verify by recomputing from current state" — always returns valid. Any DB-level edit to old rows is silently absorbed on the next append.
- **exploit_path:** Admin or data-fix script edits a historical HITL approval's `comments` field. The next status transition on that review rewrites all hashes. `verify_audit_chain` returns True. The platform has a cryptographically-clean audit trail of forged history.
- **recommended_fix:** Hashes for existing entries MUST be immutable. Compute new entry hash from the LAST persisted entry_hash; insert only the new row; never touch existing rows. Add DB triggers preventing UPDATE on `entry_hash`, `comments`, `action`, `old_status`, `new_status`, `actor_id`, `timestamp`.
- **blast_radius:** touches HIPAA contract
- **regulatory_touch:** HIPAA §164.312(b), §164.312(c)(1); EU AI Act Art.12; FDA 21 CFR Part 11 §11.10(e)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(c)(1) and 21 CFR Part 11 §11.10(e)
- 🏛 ARCH-FOLLOWUP — requires append-only schema + trigger redesign

#### CRIT-003 — HITL chain verification always returns False (timezone-format mismatch)
- **Source:** REVIEW.logic.md (CRIT-002 defect B)
- **Category:** audit
- **file:line:** `policy_engine/routes/clinical/hitl.py:126,139,160` ↔ `policy_engine/domain/clinical/hitl.py:87-98`
- **description:** `HITLAuditEntry.compute_hash()` includes timestamp as a string. Existing entries are reconstructed with `e.timestamp.isoformat()` (carries tz info), new entries written with `datetime.utcnow().isoformat()` (naive). Strings differ → `verify_audit_chain()` returns False for every chain with >1 entry.
- **exploit_path:** Compliance verify endpoint reports chain_valid=False for ALL chains, making genuinely tampered chains indistinguishable from clean ones. The audit control is non-operational.
- **recommended_fix:** Normalize all timestamps to UTC-naive ISO on both write and read-back.
- **blast_radius:** touches HIPAA contract
- **regulatory_touch:** HIPAA §164.312(b)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(b)

#### CRIT-004 — `/v1/clinical/hitl/*` endpoints perform no tenant filtering (read + write)
- **Source:** REVIEW.healthcare.md (CRIT-002)
- **Category:** tenancy
- **file:line:** `policy_engine/routes/clinical/hitl.py:170-184` (list), `226-234` (get), `363-410` (audit-trail), assign/approve/reject/escalate endpoints
- **description:** None of the list/get/state-mutation endpoints filter by `current_user.organization_id`. `_get_review_or_404` checks only `HITLReview.id == review_id`. Every authenticated user with `hitl_reviews:read` can enumerate, read, AND approve/reject any other tenant's HITL queue.
- **exploit_path:** ORG_ADMIN at clinic A calls `GET /v1/clinical/hitl/reviews` and sees every pending review from every clinic on the platform — AI decisions, reasons, risk scores, organization_ids. They can then `POST /approve` on a competitor's high-risk review, silently overriding its workflow. Cross-tenant write logged with their actor_id but defended by no tenant check.
- **recommended_fix:** Add `HITLReview.organization_id == current_user.organization_id` to every query. On POST, ignore `payload.organization_id` and force `current_user.organization_id`. Regression test asserting 404 across orgs.
- **blast_radius:** touches HIPAA contract
- **regulatory_touch:** HIPAA §164.502(a), §164.312(a)(1); GDPR Art.32
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1), §164.502

#### CRIT-005 — Prior-auth chain cannot detect tail deletion; no monotonic seq_no
- **Source:** REVIEW.logic.md (CRIT-003)
- **Category:** audit-chain / gap-detection
- **file:line:** `policy_engine/domain/finance/prior_auth.py:67-80`, `policy_engine/routes/finance/prior_auth.py:109-165`
- **description:** `verify_chain()` iterates records and checks each hash against `compute_record_hash(record_data, prev_hash)`. This detects in-place tampering and middle-row deletion. It does NOT detect tail deletion: a truncated prefix is internally consistent and returns `(True, None)`. `PriorAuthChainStatus.total_records` is stored but never compared across consecutive verifications. There is no `seq_no` column, no external anchor.
- **exploit_path:** Insider with DB access deletes the 50 most recent denials. Admin runs `GET /v1/finance/prior-auth/verify-chain`. Verifier returns valid. PriorAuthChainStatus written with `chain_valid=True`, `total_records=N-50`. No alert. Deletions are undetectable.
- **recommended_fix:** (1) Compare `len(records)` to previous `PriorAuthChainStatus.total_records`; decrease = CRITICAL alert. (2) Add `seq_no BIGINT NOT NULL UNIQUE` column; include in hash; check for gaps. (3) Publish chain-tip hash to an append-only external log after each verification.
- **blast_radius:** touches HIPAA contract
- **regulatory_touch:** HIPAA §164.312(b); CMS-0057-F; FDA 21 CFR Part 11.10(e)
- 🔴 HUMAN-REVIEW-REQUIRED — CMS-0057-F and HIPAA §164.312(b)

#### CRIT-006 — Stripe `customer.subscription.updated` never writes `org.tier`
- **Source:** REVIEW.logic.md (CRIT-001)
- **Category:** billing / state-machine
- **file:line:** `policy_engine/routes/billing/clinic.py:321-339, 396-403`
- **description:** `_handle_subscription_updated()` updates only billing metadata. It never reads a new tier from Stripe and never writes `org.tier`. The `_HANDLERS` dict routes BOTH `customer.subscription.created` AND `customer.subscription.updated` to this function. Subscriptions created via the Stripe customer portal (no `checkout.session.completed`) leave the org at TIER_ENTERPRISE permanently. Plan changes are silently ignored for tier.
- **exploit_path:** Clinic subscribes via the Stripe portal. `customer.subscription.created` fires. Subscription_status persists; tier stays `enterprise`. Clinic gets free Enterprise access. Or: clinic upgrades plan; tier never updates; paid clinic features remain locked.
- **recommended_fix:** Extract tier from Stripe subscription plan metadata inside `_handle_subscription_updated()`; write `org.tier = resolved_tier` when it differs and status is `active`/`trialing`.
- **blast_radius:** touches enterprise + HIPAA contract
- **regulatory_touch:** HIPAA §164.312(a)(1) — tier divergence grants PHI-adjacent access beyond contracted scope
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1)

#### CRIT-007 — JWT blacklist not checked in `authenticate_request`
- **Source:** REVIEW.security.md (CRIT-001)
- **Category:** auth
- **file:line:** `policy_engine/auth/rbac.py:88-94`
- **description:** `authenticate_request` decodes JWTs but never calls `get_token_blacklist().is_blacklisted(jti)`. `get_current_user` does check the blacklist. `authenticate_request` is the dependency used by audit, agents, alerts, policies. A logged-out user's token remains valid against those routes for the full 24h TTL.
- **exploit_path:** Attacker steals token. Victim logs out (blacklist hit). Attacker continues to write audit records, delete agents, modify policies via the four route groups for up to 24h. With Redis-fallback in-memory blacklist, logout on worker A is invisible to worker B regardless.
- **recommended_fix:** Add same blacklist check in `authenticate_request` (mirror lines 44-52 of `get_current_user`).
- **blast_radius:** touches enterprise
- **regulatory_touch:** HIPAA §164.312(b)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(b)

#### CRIT-008 — Audit-log retention deletes without legal-hold gate or archive-durability confirmation
- **Source:** REVIEW.database.md (CRIT-001)
- **Category:** retention / audit
- **file:line:** `policy_engine/services/audit_retention.py:120-141`
- **description:** Bulk DELETE on `audit_logs` rows older than 365 days with no legal-hold check, no archive-durability confirmation, no FK coordination. `alerts.audit_log_id` is a bare String column with no FK — after deletion alerts have dangling pointers permanently. HIPAA §164.312(b) implies a 6-year retention via §164.530(j); 365-day hard delete violates that.
- **exploit_path:** Daily retention job fires. Audit rows from a then-active patient encounter are deleted at day 366. A regulator subpoena six months later returns "no records." Alerts that referenced those rows show evidence-trail gaps with no recovery path.
- **recommended_fix:** (1) Add `legal_hold` boolean column; exclude from purge. (2) Convert `alerts.audit_log_id` to a real FK with `ON DELETE SET NULL` or RESTRICT. (3) Verify archive-backend ETag round-trip before delete. (4) Use `archive_and_delete()` exclusively; remove duplicated path in `run_retention_policy`.
- **blast_radius:** touches HIPAA contract
- **regulatory_touch:** HIPAA §164.312(b), 45 CFR §164.530(j)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(b)

#### CRIT-009 — Migration 006 is a permanent no-op; PostgreSQL `userrole` enum missing all healthcare roles
- **Source:** REVIEW.database.md (CRIT-002)
- **Category:** migration / tenancy
- **file:line:** `alembic/versions/2024_02_13_0000-006_expand_user_roles.py:20-28`
- **description:** Migration 006 intentionally skips on SQLite, but no equivalent runs against PostgreSQL. The `userrole` enum still contains only `ADMIN`, `ANALYST`, `VIEWER`. Eight declared roles (`cmio`, `data_scientist`, `compliance_officer`, `clinical_user`, `system_admin`, …) cannot be inserted in production.
- **exploit_path:** Admin creates a CMIO user. PostgreSQL rejects `INSERT` with "invalid input value for enum userrole". API returns 500. CMIO, DATA_SCIENTIST, COMPLIANCE_OFFICER, CLINICAL_USER, SYSTEM_ADMIN cannot be persisted. All RBAC paths gated on these roles are broken.
- **recommended_fix:** Add a new migration with `op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'cmio';")` etc., outside a transaction block. Reconcile the `ADMIN`/`ORG_ADMIN` alias collision.
- **blast_radius:** touches enterprise
- **regulatory_touch:** none (operational breakage)

#### CRIT-010 — `organization_id` is nullable on every multi-tenant table
- **Source:** REVIEW.database.md (CRIT-003)
- **Category:** tenancy / audit
- **file:line:** `policy_engine/models/audit_log.py:52`, `models/prior_auth.py:26`, `models/alert.py:52`, +20 others
- **description:** `organization_id` declared `nullable=True` everywhere; no NOT NULL constraint at DB layer. A missing tenant-id in any handler silently creates a row with `organization_id=NULL`. Such rows are invisible to tenant-scoped queries but ARE returned by unscoped admin queries.
- **exploit_path:** A bug or race during onboarding creates an AuditLog with `organization_id=NULL`. It surfaces in every org's admin dashboard if the dashboard misses a filter. A compliance officer at Tenant A sees Tenant B's audit events for any NULL-org row.
- **recommended_fix:** Backfill NULLs; ALTER COLUMN ... SET NOT NULL on `audit_logs`, `prior_auth_records`, `alerts`, `hitl_reviews`, `shadow_ai_detections`, `scribe_audits`, `model_cards`, `bias_audits`, `revenue_cycle_audits`, `risk_scores`, `clinic_ai_tools`, `clinic_ai_observations`, `clinic_report_artifacts`. Change CRITICAL-table FKs to `ondelete="RESTRICT"`.
- **blast_radius:** touches HIPAA contract + enterprise
- **regulatory_touch:** HIPAA §164.312(a)(1), §164.312(b)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1), §164.312(b)
- 🏛 ARCH-FOLLOWUP — evaluate PostgreSQL RLS as defense-in-depth

### dashboard

#### CRIT-011 — JWT + User object in localStorage (XSS exfiltration + client-side role forge)
- **Source:** REVIEW.typescript.md (CRIT-001)
- **Category:** auth / xss
- **file:line:** `dashboard/src/api/client.ts:82-99`
- **description:** JWT access token AND serialised `User` object (role, tier) live in localStorage. Any XSS exfiltrates both. `JSON.parse(userStr)` at line 95 has no schema validation — an attacker can write `{role:'system_admin', tier:'enterprise'}` to localStorage and `AuthContext.getUser()` serves it without challenge, passing every client-side `ProtectedRoute requiredRoles` check.
- **exploit_path:** (1) XSS payload → `localStorage.getItem('access_token')` exfiltrates a live Bearer JWT. (2) Same attacker writes a forged `user` object to localStorage; AppLayout shows admin navigation; all client-only role gates pass.
- **recommended_fix:** Move tokens to HttpOnly cookies. Short-term: validate deserialised user via Zod before trusting; never cache role/tier in localStorage — re-derive from validated server response on every `validateToken`.
- **blast_radius:** touches enterprise + HIPAA contract
- **regulatory_touch:** HIPAA §164.312(a)(2)(i)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(2)(i)

#### CRIT-012 — All `/clinic/*` routes lack tier guard at the routing layer
- **Source:** REVIEW.typescript.md (CRIT-002)
- **Category:** rbac / tenancy
- **file:line:** `dashboard/src/App.tsx:429-441`
- **description:** All 11 `/clinic/*` routes (BAA signing, compliance PDF download, shadow-AI dashboard, Stripe billing portal) are wrapped only in `ProtectedRoute` with NO `requiredTiers`. Tier check exists only in the sidebar (cosmetic). Authenticated enterprise-tier user types `/clinic/settings/compliance` and renders the BAA form unchallenged. Directly violates CLINIC_TIER_BLUEPRINT §9 ("tier flag is the ONLY enforcement surface").
- **exploit_path:** Enterprise-tier admin types `/clinic/settings/compliance` in the URL bar. ProtectedRoute passes. BAA form renders. POST to `/v1/clinic/baa/accept` succeeds (server has no role/tier check either — see CRIT-013 / HIGH-006). Same path applies to `/clinic/reports` (PDF download), `/clinic/shadow-ai` (PHI-adjacent), `/clinic/settings/billing` (Stripe portal).
- **recommended_fix:** Extend `ProtectedRoute` to accept `requiredTiers?: TierKey[]`. Wrap all 11 `/clinic/*` routes with `requiredTiers={CLINIC_ALL_TIERS}`. Server-side enforcement must remain mandatory.
- **blast_radius:** touches enterprise + HIPAA contract
- **regulatory_touch:** HIPAA §164.312(a)(1)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1)

#### CRIT-013 — JWT sent as URL query parameter on every WebSocket connection
- **Source:** REVIEW.typescript.md (CRIT-003)
- **Category:** auth
- **file:line:** `dashboard/src/hooks/useWebSocket.ts:138-143`
- **description:** `buildWsUrl()` appends the JWT as `?token=<JWT>` on every WS URL. Query strings land in server access logs, CDN/proxy logs, browser history, and `Referer` headers. The TLS body is encrypted but logs capture the URL with the token in clear text.
- **exploit_path:** Any infra log with read access (S3 log bucket, log aggregator, CloudFront access log) yields a live Bearer JWT. Replayable against the REST API for any action the user's role permits, including reading clinical/shadow-AI PHI-adjacent data.
- **recommended_fix:** One-time WS ticket pattern: client `POST /v1/ws/ticket` → server returns short-lived (<30s) single-use opaque ticket; client opens `ws://.../ws/dashboard?ticket=<id>`; server exchanges and discards. JWT never appears in any URL.
- **blast_radius:** touches enterprise + HIPAA contract
- **regulatory_touch:** HIPAA §164.312(e)(2)(i)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(e)(2)(i)

---

## HIGH Findings

### policy_engine — tenancy

#### HIGH-001 — Admin Shadow-AI + regulatory listing endpoints cross-tenant
- **Source:** REVIEW.python.md (HIGH-002)
- **file:line:** `policy_engine/routes/admin/shadow_ai.py:177-192`, `policy_engine/routes/regulatory/{adverse_events,pms_reports,technical_files,risk_scores}.py`
- **description:** `list_detections()` queries without `organization_id` filter. Regulatory listing endpoints inconsistently apply scoping. Any admin-tier user reads every org's shadow-AI detections (PHI risk levels, source IPs, destination hosts, departments).
- **recommended_fix:** Apply `.filter(...organization_id == current_user.organization_id)` consistently.
- **regulatory_touch:** HIPAA §164.312(a)(1); EU AI Act Art.72
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1)

#### HIGH-002 — `create_hitl_review` accepts `organization_id` from request body (tenant spoofing)
- **Source:** REVIEW.healthcare.md (HIGH-001)
- **file:line:** `policy_engine/routes/clinical/hitl.py:204`
- **description:** `HITLReviewCreate.organization_id` is read from payload and written verbatim. Even after CRIT-004 read-side fix, write-side allows planting entries into another tenant's queue.
- **recommended_fix:** Remove `organization_id` from the schema; force `current_user.organization_id`.
- **regulatory_touch:** HIPAA §164.312(a)(1)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1)

#### HIGH-003 — Transparency-portal endpoints unauthenticated, leak org metadata + acknowledgement spoofing
- **Source:** REVIEW.healthcare.md (HIGH-003)
- **file:line:** `policy_engine/routes/admin/transparency.py:139-149, 239-267, 270-285, 288-297`
- **description:** `GET /v1/transparency`, `/{id}`, `/{id}/versions`, `POST /{id}/acknowledge` all unauthenticated. Response leaks `organization_id`, `created_by`, plus free-text `bias_considerations`, `evidence_base`, `known_limitations`. `acknowledge` accepts arbitrary `user_id` and `role` — pollutes adoption metrics.
- **recommended_fix:** Require auth on list/acknowledge; strip org-attribution from public response; bind acknowledge to `current_user.id`; rate-limit.
- **regulatory_touch:** HIPAA §164.502(b); ONC HTI-1 does not authorize org-attribution leakage

#### HIGH-004 — Transparency `update`/`publish` lack tenant check
- **Source:** REVIEW.healthcare.md (MED-005) — promoted to HIGH due to org-cross attack surface
- **file:line:** `policy_engine/routes/admin/transparency.py:300-346`
- **description:** ORG_ADMIN can publish or rewrite any org's transparency record. Combined with HIGH-003 (public listing), one tenant can publish false algorithm-transparency claims on behalf of another.
- **recommended_fix:** Add `record.organization_id == current_user.organization_id` check (exempt SYSTEM_ADMIN).
- **regulatory_touch:** HIPAA §164.312(a)(1); ONC HTI-1 integrity

#### HIGH-005 — `subscription_lifecycle` ignores `unpaid` status (clinic keeps access after non-payment)
- **Source:** REVIEW.logic.md (HIGH-002)
- **file:line:** `policy_engine/services/subscription_lifecycle.py:87-100`
- **description:** Revert only fires for `sub_status == "canceled"`. Stripe dunning lifecycle (`active → past_due → unpaid → canceled`) can stop at `unpaid` indefinitely (invoice billing, no `cancel_at_period_end`). Clinic retains tier indefinitely.
- **recommended_fix:** Extend guard to `("canceled", "unpaid")` and consider `past_due` past `current_period_end`.
- **regulatory_touch:** HIPAA §164.312(a)(1)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1)

### policy_engine — auth / baa / phi

#### HIGH-006 — Any clinic-tier user can self-accept the BAA (no role check)
- **Source:** REVIEW.healthcare.md (HIGH-004)
- **file:line:** `policy_engine/routes/clinic/baa.py:56-122`
- **description:** `POST /v1/clinic/baa/accept` has no role check. A VIEWER/CLINICAL_USER can sign the org's BAA. Accepter name/title/legal-name accepted as user-supplied strings with no verification.
- **exploit_path:** Front-desk receptionist with VIEWER role clicks Accept. Clinic is contractually bound under HIPAA with click-through evidence; owner never approved. All BAA-gated routes (tools, reports, policy templates, shadow-ai) unlock under a legally-invalid BAA.
- **recommended_fix:** `_require_admin(current_user)` at the top of `accept`. Email-confirmation step to org owner. Audit log flags accepter's role.
- **regulatory_touch:** HIPAA §164.502(e), §164.504(e)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.502(e), §164.504(e)

#### HIGH-007 — `update_practice` writes phone/address without PHI scan
- **Source:** REVIEW.security.md (HIGH-003)
- **file:line:** `policy_engine/routes/clinic/settings.py:75-96`
- **description:** Unlike tool routes (which call `reject_if_phi_present`), the practice-settings update has no PHI check. Phone numbers and addresses pasted from a patient record persist to `org.settings` undetected.
- **recommended_fix:** Call `reject_if_phi_present({...})` at the top of `update_practice`.
- **regulatory_touch:** HIPAA §164.530(c)(1)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.530(c)(1)

#### HIGH-008 — Scribe-auditor embeds 200 chars of redacted-note claim text in stored finding `description`
- **Source:** REVIEW.healthcare.md (HIGH-005)
- **file:line:** `policy_engine/services/scribe_auditor.py:332-344`
- **description:** Regex redaction is not exhaustive. Residual PHI in unattributed-claim text lands in `ScribeAuditResult.description`, viewable by admins via `/v1/admin/scribe-audits`.
- **recommended_fix:** Replace embedded text with a stable token (claim_index or SHA-256); keep full text in an access-controlled ephemeral artifact or re-redact before storage.
- **regulatory_touch:** HIPAA §164.514(b), §164.502(a)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.514

### policy_engine — audit-chain

#### HIGH-009 — Prior-auth chain ordered by mutable `created_at`; no FK protection from org delete
- **Source:** REVIEW.healthcare.md (HIGH-002)
- **file:line:** `policy_engine/routes/finance/prior_auth.py:51-54, 109-165`; `policy_engine/models/prior_auth.py:18,26`
- **description:** `verify_chain` walks records ordered by `created_at.asc()`. `created_at` is mutable, no `server_default`, no immutability constraint. `organization_id` and `human_reviewer_id` FKs use `ondelete="SET NULL"`. No DB-level append-only trigger.
- **exploit_path:** Insider with DB write access edits `created_at` on two rows to swap order. `prev_record_hash → record_hash` matches when traversed by manipulated timeline. Chain validates against a tampered history.
- **recommended_fix:** Traverse by `prev_record_hash → record_hash` graph, not by `created_at`. Add DB triggers preventing UPDATE/DELETE. FK to `ondelete="RESTRICT"`.
- **regulatory_touch:** HIPAA §164.312(b); CMS-0057-F; 21 CFR Part 11
- 🔴 HUMAN-REVIEW-REQUIRED — CMS-0057-F, 21 CFR Part 11 §11.10(e)

#### HIGH-010 — No scheduled prior-auth chain verification job
- **Source:** REVIEW.healthcare.md (HIGH-006)
- **file:line:** `policy_engine/routes/finance/prior_auth.py` (no cron) + `services/scheduler.py`
- **description:** Chain integrity only checked on-demand via `GET /verify-chain`. Orgs that never call the endpoint have zero integrity assurance. Combined with CRIT-005 + HIGH-009, undetected breaks can persist indefinitely.
- **recommended_fix:** Daily scheduled job runs `verify_chain` per org; writes `PriorAuthChainStatus`; CRITICAL alert on `chain_valid=False`.
- **regulatory_touch:** HIPAA §164.312(b); 21 CFR Part 11 §11.10(e)
- 🔴 HUMAN-REVIEW-REQUIRED

#### HIGH-011 — `hitl_audit_trail.entry_hash` has `server_default=''` (chain bypass via empty-string)
- **Source:** REVIEW.database.md (HIGH-005)
- **file:line:** `policy_engine/models/hitl.py:59`; `alembic/versions/2024_02_16_0000-009_clinical_governance.py:194`
- **description:** Empty default means any direct DB insert without explicitly-computed hash stores `''`. Verifier computes `sha256("" + content)`; attacker who controls content can match it.
- **recommended_fix:** `CHECK (length(entry_hash) = 64)`. Remove `server_default`; make `nullable=False` with no default.
- **regulatory_touch:** HIPAA §164.312(b)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(b)

#### HIGH-012 — All `DateTime` columns are `TIMESTAMP WITHOUT TIME ZONE` (audit timestamp ambiguity)
- **Source:** REVIEW.database.md (HIGH-004)
- **file:line:** `alembic/versions/2024_02_09_1200-001_initial_schema.py:57`, `policy_engine/models/audit_log.py:40` (and all DateTime columns)
- **description:** All audit-relevant timestamps stored without timezone. DST transitions, server-region migrations, or driver changes produce ambiguous interpretation.
- **recommended_fix:** Migrate all DateTime columns to `sa.DateTime(timezone=True)` (TIMESTAMPTZ). Application: switch `datetime.utcnow()` → `datetime.now(tz=timezone.utc)`.
- **regulatory_touch:** HIPAA §164.312(b)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(b)

#### HIGH-013 — Migration 017 backfill UPDATE wraps `except Exception: pass`
- **Source:** REVIEW.database.md (HIGH-003)
- **file:line:** `alembic/versions/2024_02_24_0000-017_clinic_compliance.py:56-72`
- **description:** Cross-tenant alert-leak fix can silently fail (lock timeout, permission, syntax) while migration reports success.
- **recommended_fix:** Remove `except: pass`; log + re-raise; run as a separate retriable migration.
- **regulatory_touch:** HIPAA §164.312(a)(1)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1)

#### HIGH-014 — Migration 005 `downgrade()` drops tables without dropping indexes
- **Source:** REVIEW.database.md (HIGH-001)
- **file:line:** `alembic/versions/2024_02_12_0000-005_add_organizations.py:59-61`
- **description:** Partial downgrade leaves indexes orphaned; idempotency guards mask the inconsistency.
- **recommended_fix:** Explicit `op.drop_index()` for all five indexes; use IF EXISTS.

### policy_engine — billing / async / logic

#### HIGH-015 — Sync `requests` library used inside async handler chain
- **Source:** REVIEW.python.md (HIGH-001)
- **file:line:** `policy_engine/services/slack_service.py:66, 91, 267` called from `policy_engine/routes/policy_check.py:199`
- **description:** Up to 45s of event-loop blocking when Slack degrades. Self-induced DoS exactly when alerts are most needed.
- **recommended_fix:** Switch to `httpx.AsyncClient`; `asyncio.sleep`; or offload via `run_in_executor`.

#### HIGH-016 — Internal exception string echoed verbatim to API caller
- **Source:** REVIEW.python.md (HIGH-003)
- **file:line:** `policy_engine/routes/policy_check.py:294-298`
- **description:** `reason=f"Policy evaluation failed: {str(e)}…"` and `metadata={'error': str(e)}` leak DB connection strings, ORM column names, stack-trace fragments to third-party AI agents.
- **recommended_fix:** Generic "Internal error; action blocked for safety"; keep `exc_info=True` in server-side log only.

#### HIGH-017 — Stripe webhook org-resolution full-table-scans Organization for every retry
- **Source:** REVIEW.python.md (HIGH-004)
- **file:line:** `policy_engine/routes/billing/clinic.py:256-279`
- **description:** `_resolve_org_for_session()` and `_resolve_org_by_customer()` iterate every org and inspect `org.settings["billing"]` JSON. O(N) per webhook event.
- **recommended_fix:** Promote `stripe_customer_id` to an indexed column on Organization (or BillingProfile).
- **regulatory_touch:** Stripe terms (webhook handler latency SLA)
- 🏛 ARCH-FOLLOWUP

#### HIGH-018 — Bias-audit publish gate has documented exception path but no implementation
- **Source:** REVIEW.logic.md (HIGH-001)
- **file:line:** `policy_engine/routes/clinical/model_cards.py:617-676`; `routes/clinical/bias_audits.py:174-224`
- **description:** Guidance text says "document approved exception and re-run." But no `exception_approved` field on `BiasAuditModel`; no query against HITLReview status; only `BIAS_AUDIT_PUBLISH_GATE=false` env disables the gate org-wide.
- **recommended_fix:** Add `exception_approved` + `exception_reviewer_id`; check linked HITL review status before publish.
- **regulatory_touch:** EU AI Act Art.10(4)
- 🔴 HUMAN-REVIEW-REQUIRED — EU AI Act Art.10(4)

#### HIGH-019 — Alert acknowledge schema has no comment field server-side
- **Source:** REVIEW.logic.md (HIGH-003)
- **file:line:** `policy_engine/models/schemas.py:291-293`; `services/alert_service.py:112-143`
- **description:** `AlertAcknowledge` is just `acknowledged_by: str`. No comment is stored even for CRITICAL alerts. Post-incident audit cannot reconstruct decision context.
- **recommended_fix:** Add `comment: Optional[str]`; require non-empty for `severity in (critical, high)`; persist on Alert row.
- **regulatory_touch:** HIPAA §164.308(a)(1)(ii)(D); EU AI Act Art.9.7
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.308(a)(1)(ii)(D)

#### HIGH-020 — HITL SLA is wall-clock only; `escalation_tier()` is never invoked by any scheduler
- **Source:** REVIEW.logic.md (HIGH-004)
- **file:line:** `policy_engine/services/hitl_auto_service.py:229-233`; `domain/clinical/hitl.py:47-74`
- **description:** Urgent (4h) SLA created at 11pm Friday expires by 3am Saturday. `escalation_tier()` exists but no scheduler invokes it — the entire escalation system is dead code in production.
- **recommended_fix:** Business-hours-aware SLA calculator (per-org timezone); wire `escalation_tier()` into the scheduler.
- **regulatory_touch:** EU AI Act Art.9.7; FDA SaMD PCCP; MDR PSUR
- 🔴 HUMAN-REVIEW-REQUIRED — EU AI Act Art.9.7

#### HIGH-021 — Model-card lifecycle: REVIEW→DRAFT unrouted, PUBLISHED→REVIEW absent, updates blocked on PUBLISHED
- **Source:** REVIEW.logic.md (HIGH-005)
- **file:line:** `policy_engine/domain/clinical/model_card.py:15-19`; `routes/clinical/model_cards.py:528-573`
- **description:** Reviewer cannot reject a card back to draft (no route). Published card with an error has no amendment path — only RETIRE.
- **recommended_fix:** Add POST reject (REVIEW→DRAFT) and reopen-review (PUBLISHED→REVIEW) routes; extend `update_model_card` for active re-review workflow.
- **regulatory_touch:** MDR PSUR; EU AI Act Art.9.7; FDA SaMD PCCP
- 🔴 HUMAN-REVIEW-REQUIRED — MDR PSUR

### policy_engine — index / schema

#### HIGH-022 — `prior_auth_records` missing composite index `(organization_id, created_at)`
- **Source:** REVIEW.database.md (HIGH-002)
- **file:line:** `policy_engine/models/prior_auth.py:10-26`
- **description:** Chain verification triggers seq scan + sort. At 50k records produces multi-second queries, pool exhaustion.
- **recommended_fix:** `CREATE INDEX ix_prior_auth_records_org_created ON prior_auth_records (organization_id, created_at);`

#### HIGH-023 — `audit_logs` missing composite index `(organization_id, timestamp)`
- **Source:** REVIEW.database.md (HIGH-006)
- **file:line:** `policy_engine/models/audit_log.py:39-52`
- **description:** Seven single-column indexes, none serves the hot dashboard query. Index intersection + sort at 2M rows produces P95 > 2s.
- **recommended_fix:** `CREATE INDEX ix_audit_logs_org_timestamp ON audit_logs (organization_id, timestamp DESC);`
- 🏛 ARCH-FOLLOWUP — evaluate monthly partitioning for tables >10M rows

### dashboard

#### HIGH-024 — Enterprise routes missing role guards (direct-URL bypass)
- **Source:** REVIEW.typescript.md (HIGH-001)
- **file:line:** `dashboard/src/App.tsx:401-414`
- **description:** `/clinical/model-cards`, `/clinical/bias-audits`, `/clinical/drift`, `/clinical/hitl/**`, `/admin/shadow-ai`, `/admin/scribe-audits`, `/transparency` have no `requiredRoles` prop. VIEWER-role user types URL and renders the page.
- **recommended_fix:** Derive `requiredRoles` from `NAV_SECTIONS.allowedRoles`; wrap every sensitive enterprise route.
- **regulatory_touch:** HIPAA §164.312(a)(1)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(a)(1)

#### HIGH-025 — `JSON.parse(userStr)` with no try/catch silently logs the user out on corrupt storage
- **Source:** REVIEW.typescript.md (HIGH-002)
- **file:line:** `dashboard/src/api/client.ts:94-96`
- **recommended_fix:** Wrap in try/catch; `clearUser()`+return null on parse error.

#### HIGH-026 — Unsafe `TierKey` cast without runtime validation
- **Source:** REVIEW.typescript.md (HIGH-003)
- **file:line:** `dashboard/src/contexts/AuthContext.tsx:184`; `components/layout/AppLayout.tsx:121-122`
- **description:** `(user?.tier as TierKey)` suppresses type checks. Unknown tier from server collapses sidebar to empty with no error.
- **recommended_fix:** Validated accessor: `isClinicTier(rawTier) || rawTier === 'enterprise' ? rawTier as TierKey : 'enterprise'`.

#### HIGH-027 — WebSocket reconnect race (unstable callback identity creates duplicate sockets)
- **Source:** REVIEW.typescript.md (HIGH-004)
- **file:line:** `dashboard/src/hooks/useWebSocket.ts:39-93`; `pages/Dashboard.tsx:66-72`
- **recommended_fix:** Wrap callbacks in `useCallback` or store in refs inside `useWebSocket`.

#### HIGH-028 — `ApiClient` generic methods typed as `any` (5 ESLint warnings)
- **Source:** REVIEW.typescript.md (HIGH-005)
- **file:line:** `dashboard/src/api/client.ts:165-190`
- **recommended_fix:** Generic typing `async post<T, D = Record<string, unknown>>(...)`; explicit payload types for auth/BAA/billing.

#### HIGH-029 — Dual WebSocket + 60s polling races overwrite WS data with stale REST
- **Source:** REVIEW.typescript.md (HIGH-006)
- **file:line:** `dashboard/src/pages/Dashboard.tsx:87-91`
- **recommended_fix:** Only poll when WS is disconnected.

#### HIGH-030 — `import.meta` cast to `any` in Reports.tsx allows BASE_URL hijack
- **Source:** REVIEW.typescript.md (HIGH-007)
- **file:line:** `dashboard/src/pages/clinic/Reports.tsx:56`
- **description:** Cast to any suppresses type checking on `VITE_API_BASE_URL`. A compromised CI/CD setting can redirect token-bearing downloads to attacker.
- **recommended_fix:** Remove cast; use typed `import.meta.env.VITE_API_BASE_URL`; same-origin check at startup; route via `apiClient.getBlob()`.
- **regulatory_touch:** HIPAA §164.312(e)(2)(i)
- 🔴 HUMAN-REVIEW-REQUIRED — HIPAA §164.312(e)(2)(i)

### extension

#### HIGH-031 — Extension endpoint URL is user-configurable with no validation
- **Source:** REVIEW.security.md (HIGH-002)
- **file:line:** `clinic-extension/options.js:15-17`, `clinic-extension/background.js:69`
- **description:** Any URL typed into options is used verbatim in `fetch()`. Bearer-equivalent `X-Clinic-Extension-Token` header is sent with every POST.
- **exploit_path:** Rogue admin or social-engineered user sets endpoint to `https://evil.example.com`. Every observation POST (with token) flows to attacker, who can replay against the real API.
- **recommended_fix:** Validate URL scheme + hostname in options.js; manifest CSP `connect-src` restricted to production domain.

### policy_engine — ssrf

#### HIGH-032 — SSRF IPv6 blocklist missing ULA, link-local, IPv4-mapped, NAT64
- **Source:** REVIEW.security.md (HIGH-001)
- **file:line:** `policy_engine/services/url_validator.py:21-22`
- **description:** `PRIVATE_IPV6` contains only `::1/128`. `fc00::/7` ULA, `fe80::/10` link-local, `::ffff:0:0/96` IPv4-mapped (incl. `::ffff:169.254.169.254` AWS IMDS) all pass.
- **recommended_fix:** Expand list to include ULA, link-local, IPv4-mapped, NAT64, Discard. Add `is_multicast` check.

---

## MEDIUM Findings (grouped, condensed)

All MEDIUM findings are in `policy_engine`. Refer to source files for full blocks.

### Security
- **MED-001 — CORS `allow_headers: ["*"]`** — `policy_engine/config.py:21`. Widens future header surface; could interact with CSRF middleware additions. *Source: REVIEW.security.md (MED-001).*
- **MED-002 — JWT 24h non-rotating** — `policy_engine/config.py:39`, `routes/auth.py:140-172`. Refresh issues new token without revoking old. **HIPAA §164.312(d)** 🔴. *Source: REVIEW.security.md (MED-002).*
- **MED-003 — Stripe webhook email-match fallback enables cross-tenant tier flip** — `policy_engine/routes/billing/clinic.py:248-270`. Email-based fallback in `_resolve_org_for_session` lets an attacker who knows an org's billing email flip its tier. **Stripe terms**. *Source: REVIEW.security.md (MED-003).*
- **MED-004 — Rate limiter uses `request.client.host` behind reverse proxy** — `policy_engine/middleware/rate_limiter.py:49`. All unauth traffic collapses into one bucket; credential-stuffing on `/v1/auth/login` is effectively unbounded per attacker IP. *Source: REVIEW.security.md (MED-004).*
- **MED-005 — Extension token SHA-256 unsalted** — `policy_engine/routes/clinic/shadow_ai.py:37-38`. Inconsistent with Argon2id used elsewhere. *Source: REVIEW.security.md (MED-005).*

### Healthcare / PHI
- **MED-006 — PHI sniffer is US-format only** — `policy_engine/services/phi_text_check.py:26-58`. Missing NHS, SIN, ICD-10 as PID, E.164 phone, EU date formats. **HIPAA §164.514(b); GDPR Art.4(1)**. *Source: REVIEW.healthcare.md (MED-001).*
- **MED-007 — PHI redaction regex gaps** — `policy_engine/infrastructure/security/phi_redaction.py:41-43, 95`. NAME requires honorific; DATE misses ISO/EU; MRN requires literal prefix; Presidio detected but unused. **HIPAA §164.514(b)**. *Source: REVIEW.healthcare.md (MED-002).*
- **MED-008 — Error handler logs `str(exc)` with raw input** — `policy_engine/middleware/error_handler.py:22-31`. Pydantic ValidationError contains raw FHIR fields incl. patient name/DOB. **HIPAA §164.312(a)(2)(iv)**. *Source: REVIEW.healthcare.md (MED-003).*
- **MED-009 — FHIR ingest logs exception with raw resource data** — `policy_engine/services/fhir_service.py:217`. Same risk class as MED-008 for FHIR identifiers. **HIPAA §164.312(b)**. *Source: REVIEW.healthcare.md (MED-004).*
- **MED-010 — Clinic PDF audit-count silently fails-closed for NULL-org rows** — `policy_engine/services/clinic_pdf_report.py:113-130`. Future regression that writes NULL-org audit silently produces zero counts. **HIPAA §164.312(b)**. *Source: REVIEW.healthcare.md (MED-006).*

### Python
- **MED-011 — `FHIRClient._get_token()` no httpx timeout** — `policy_engine/infrastructure/external/fhir_client.py:56-69`. Hung OAuth endpoint stalls event loop indefinitely. *Source: REVIEW.python.md (MED-002).*
- **MED-012 — Async routes use sync `Session`** — `policy_engine/routes/policy_check.py:220-307` and most other routes. Sync ORM blocks event loop. `get_async_db()` exists but only some routes use it. 🏛 ARCH-FOLLOWUP. *Source: REVIEW.python.md (MED-003).*
- **MED-013 — Silent ciphertext fallback on decrypt failure** — `policy_engine/services/encryption.py:84-85`. `except Exception: return value` (ciphertext). Encrypted PHI silently served as ciphertext with no alert. **HIPAA §164.312(a)(2)(iv)** 🔴. *Source: REVIEW.python.md (MED-004).*
- **MED-014 — Extension token SHA-256 unsalted** — `policy_engine/routes/clinic/shadow_ai.py:38`. (Duplicate of MED-005 from different angle.) **HIPAA §164.312(d)**. *Source: REVIEW.python.md (MED-001).*

### Database
- **MED-015 — Migrations 004–013 use table-existence guards that skip subsequent op steps** — silently skips index/constraint additions if table pre-existed. *Source: REVIEW.database.md (MED-001).*
- **MED-016 — `prior_auth_records.request_date/decision_date` typed as String** — lexicographic ordering produces wrong compliance metrics. *Source: REVIEW.database.md (MED-002).*
- **MED-017 — ~10 enum-like text columns missing CHECK constraints** — direct DB writes (bulk imports, data scripts) can insert invalid values. Examples: `hitl_reviews.status`, `billing_events.status`, `clinic_ai_observations.severity`, `shadow_ai_detections.phi_risk_level`. *Source: REVIEW.database.md (MED-003).*
- **MED-018 — `clinic_ai_tools` missing `(org_id, status)` composite index** — *Source: REVIEW.database.md (MED-004).*
- **MED-019 — `prior_auth_records.record_hash` not UNIQUE, no length CHECK** — buggy `record_hash=''` for batch makes the chain trivially validate as anchored to `''`. **HIPAA §164.312(b)** 🔴. *Source: REVIEW.database.md (MED-005).*
- **MED-020 — Billing retention has no minimum floor** — operator setting `CLINIC_BILLING_EVENT_RETENTION_DAYS=30` violates Stripe terms; chargeback evidence lost. **Stripe terms**. *Source: REVIEW.database.md (MED-006).*
- **MED-021 — `risk_score_history.organization_id`/`risk_regulatory_mapping.organization_id` no FK** — orphaned rows accumulate forever; potential cross-org bleed if ID is reused. *Source: REVIEW.database.md (MED-007).*

### Logic / drift
- **MED-022 — PSI diverges between numpy and pure-Python paths; threshold is strict `>`** — `policy_engine/domain/clinical/drift_detector.py:38-81`; `services/drift_ingestion.py:259-261`. PSI==0.2 never alerted. **FDA SaMD PCCP**. *Source: REVIEW.logic.md (MED-001).*
- **MED-023 — Drift buffer unbounded; auto-recompute off by default; `measurement_time` overwritten on every batch** — `policy_engine/services/drift_ingestion.py:124-167, 63-65`. **FDA SaMD PCCP**. *Source: REVIEW.logic.md (MED-002).*

### Transparency tenancy
- **MED-024 — Transparency `update_practice` tenant check absence** — (already promoted to HIGH-004 above; left as cross-reference here)

---

## LOW Findings (grouped, condensed)

### policy_engine
- **LOW-001 — `patient_id` SHA-256 unsalted** — `policy_engine/routes/finance/prior_auth.py:48`. Rainbow-table reversible. **HIPAA §164.514(b)**. *Source: REVIEW.python.md (LOW-001).*
- **LOW-002 — Broad `Exception` catch swallows non-JWT exceptions in `decode_access_token`** — `policy_engine/auth/jwt_utils.py:91`. *Source: REVIEW.python.md (LOW-002).*
- **LOW-003 — BAA accept honors `X-Forwarded-For` without trusted-proxy list** — `policy_engine/routes/clinic/baa.py:86-90`. Spoofable IP undermines non-repudiation. **GDPR Art.7(1)**. *Source: REVIEW.healthcare.md (LOW-002).*
- **LOW-004 — Prior-auth chain-tail lookup not transactional (`SELECT ... FOR UPDATE` missing)** — `policy_engine/routes/finance/prior_auth.py:51-54`. Concurrent inserts can fork the chain. **HIPAA §164.312(c)(1)** 🔴. *Source: REVIEW.healthcare.md (LOW-003).*
- **LOW-005 — `get_redaction_log` returns cross-tenant rows for ORG_ADMIN** — `policy_engine/routes/phi.py:101-138`. **HIPAA §164.502(b)**. *Source: REVIEW.healthcare.md (LOW-004).*
- **LOW-006 — Redundant single-column indexes on PK columns** — across all migrations. ~5–10% INSERT overhead at scale. *Source: REVIEW.database.md (LOW-001).*
- **LOW-007 — All PK `id` columns typed as String** — TEXT PK wider than UUID; no format CHECK. 🏛 ARCH-FOLLOWUP. *Source: REVIEW.database.md (LOW-002).*
- **LOW-008 — `Organization.tier` has no CHECK constraint** — misspelled `'clinic'` would silently route to enterprise. *Source: REVIEW.database.md (LOW-003).*
- **LOW-009 — `prior_auth_records.ai_recommendation`/`final_decision` no CHECK constraint** — data-quality risk; affects chain reproducibility. *Source: REVIEW.database.md (LOW-004).*
- **LOW-010 — Stripe webhook org-resolution full-table scans** — `policy_engine/routes/billing/clinic.py:248-269`. (Same root cause as HIGH-017 but performance-only impact.) *Source: REVIEW.logic.md (LOW-001).*

### dashboard
- **LOW-011 — JWT in localStorage (XSS exfiltration risk)** — `dashboard/src/api/client.ts:82-90`. (Pre-cursor framing of CRIT-011.) *Source: REVIEW.security.md (LOW-001).*
- **LOW-012 — CSP allows `'unsafe-inline'` for script-src and style-src** — `nginx.conf:53`. *Source: REVIEW.security.md (LOW-003).*
- **LOW-013 — No HSTS; nginx listens on port 80 only** — `nginx.conf:43`. **HIPAA §164.312(e)(1)** 🔴. *Source: REVIEW.security.md (LOW-004).*

### extension
- **LOW-14 — Extension transmits full URL hash + 500-char UA** — `clinic-extension/background.js:80, 90-106`. Rainbow-table risk on predictable URL shapes. **GDPR Art.5(c)**. *Source: REVIEW.healthcare.md (LOW-001).*

### sdk
- **LOW-15 — Placeholder API keys in `sentinel/sdk/adapters/examples.py:68, 113, 152`** — secrets-scanner false positives; copy-paste risk. *Source: REVIEW.security.md (LOW-002).*

---

## ARCH-FOLLOWUP (cross-cutting refactors, no autofix)

| # | Item | Source |
|---|---|---|
| ARCH-FU-1 | Append-only audit-chain library shared by HITL + prior-auth, with monotonic `seq_no` and external anchor publishing. Prerequisite for closing CRIT-002, CRIT-003, CRIT-005, HIGH-009, HIGH-011. | logic.md ARCH-FOLLOWUP-001, healthcare.md CRIT-001 |
| ARCH-FU-2 | `TierStateMachine` service as the single writer to `Organization.tier`, with transition logging and idempotency. Closes the class of bugs in CRIT-006, HIGH-005, MED-003. | logic.md ARCH-FOLLOWUP-002 |
| ARCH-FU-3 | Promote `stripe_customer_id` from `org.settings` JSON to a dedicated indexed column (or BillingProfile table). Closes HIGH-017, LOW-010. | python.md HIGH-004, database.md cross-cutting |
| ARCH-FU-4 | Migrate async routes from sync `Session` to `AsyncSession` consistently across `policy_engine/routes/*`. Closes MED-012. | python.md MED-003 |
| ARCH-FU-5 | Enable PostgreSQL Row-Level Security as defense-in-depth behind application-layer tenant filters. Closes the class of bugs in CRIT-001, CRIT-004, CRIT-010, HIGH-001. | database.md CRIT-003 |
| ARCH-FU-6 | DB-trigger-enforced append-only constraint on `audit_logs` and `prior_auth_records` and `hitl_audit_trail` (no UPDATE/DELETE at the storage engine level). | database.md cross-cutting |
| ARCH-FU-7 | Distributed token blacklist — make Redis a hard dependency in production; fail the lifespan if Redis is unreachable. Current in-memory fallback is not multi-worker safe. | security.md ARCH-FOLLOWUP-1 |
| ARCH-FU-8 | Migrate all PK `id` columns from String to native `UUID` type; or add `CHECK (id ~ '^[0-9a-f-]{36}$')`. Cap as a dedicated migration sprint. | database.md LOW-002 |
| ARCH-FU-9 | Evaluate monthly partitioning for `audit_logs` and similar large append-only tables (>10M rows). | database.md HIGH-006 |
| ARCH-FU-10 | Model-card versioning model — published cards mutate via versioned amendment, not lifecycle rewind, preserving lineage. | logic.md HIGH-005 |

---

## Cross-cutting observations (not findings — informational)

- **PHI Redaction Engine** covers all 18 HIPAA Safe Harbor identifiers. Gaps are breadth (international formats, bare names), not architecture.
- **Clinic PDF report** is well-disciplined: only aggregates, explicit tenant filtering, path-traversal guard, no patient rows.
- **Browser extension** is correctly scoped at the data layer: `storage.local`, debounced, hashed URL, host-only payload, BAA-gated server-side. The two extension findings (HIGH-031, LOW-14) are about endpoint trust and entropy, not exfiltration of PHI.
- **BAA gate** (`require_clinic_tier_with_baa`) is correctly wired into tools, policy templates, reports, and shadow-ai ingestion. Read-side routes use the lighter `require_clinic_tier`.
- **Tier enforcement contract** (CLINIC_TIER_BLUEPRINT §9) holds for clinic write paths. Exceptions are the global `/v1/clinical/hitl/*` and `/v1/transparency/*` namespaces, which serve both tiers but lack proper tenant filtering (CRIT-004, HIGH-003).
- **Stripe signature verification, SECRET_KEY weak-key check, raw-SQL absence, `pickle`/`eval`/`yaml.load` absence, CORS production guard, report path-traversal guard, Argon2id key hashing** — all verified clean.

---

## Notes for next session

- Section files preserved alongside this consolidated report: `REVIEW.security.md`, `REVIEW.healthcare.md`, `REVIEW.python.md`, `REVIEW.typescript.md`, `REVIEW.database.md`, `REVIEW.logic.md`.
- The TypeScript reviewer's report was truncated — 5 MEDIUM and 3 LOW dashboard findings are declared in its counts table but not written. Recommended: re-dispatch the TypeScript reviewer with a narrowed scope (MEDIUM/LOW only) for completeness.
- All HIPAA, FDA 21 CFR Part 11, CMS-0057-F, MDR PSUR, EU AI Act, and Stripe-terms touchpoints have been marked 🔴 HUMAN-REVIEW-REQUIRED with the specific clause cited.
- 10 ARCH-FOLLOWUP items captured. None of them are required to remediate individual CRITICAL findings, but they are the durable structural fixes that would prevent the bug class from recurring.

---

## Pass 1 Remediation Status (branch `fix/security-and-logic-pass-1`)

### Closed in this pass — 10 atomic commits

| ID | Commit | Subject |
|---|---|---|
| HIGH-032 | `87cc6ae` | fix(security): expand SSRF IPv6 blocklist |
| HIGH-015 | `283a982` | fix(security): offload Slack send to executor inside event loop |
| HIGH-016 | `4650bab` | fix(security): redact str(exc) from /v1/policy/check fail-safe response |
| HIGH-004 | `5e5752b` | fix(security): enforce tenancy on transparency update/publish |
| HIGH-014 | `7e7d203` | fix(migration): drop named indexes in 005 downgrade |
| HIGH-031 | `bdfa8d4` | fix(security): validate extension endpoint URL before saving |
| HIGH-025 | `62588b2` | fix(dashboard): guard JSON.parse in ApiClient.getUser |
| HIGH-026 | `d533d8e` | fix(dashboard): runtime-validate TierKey with resolveTier |
| HIGH-027 | `9cac3d5` | fix(dashboard): stabilise useWebSocket callbacks via refs |
| HIGH-029 | `1de0887` | fix(dashboard): suppress polling while WebSocket is connected |

Each fix is TDD: failing test → minimal patch → green. Bandit `policy_engine sentinel -ll`: 0 Medium/High issues. New pytest suite: 36 passed. New vitest suite: 28 passed.

### Deferred — human review required

All 13 CRITICAL findings are 🔴 HUMAN-REVIEW-REQUIRED (HIPAA, FDA, EU AI Act, CMS-0057-F, MDR PSUR clauses) and were not touched in this pass per the explicit skip rule.

| ID | Title | Defer reason |
|---|---|---|
| CRIT-001 | Cross-tenant data leak on audit/agents/policies/alerts | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1)) — change touches the listing contract for four route groups; schema-shape implications for `organization_id` and PostgreSQL RLS need product/legal sign-off |
| CRIT-002 | HITL hash chain recomputed on append | 🔴 HUMAN-REVIEW (HIPAA §164.312(c)(1), 21 CFR Part 11 §11.10(e)); ARCH-FOLLOWUP-1 — append-only schema + trigger redesign |
| CRIT-003 | HITL chain timezone mismatch | 🔴 HUMAN-REVIEW (HIPAA §164.312(b)) — fix changes audit-log row shape (timestamp normalisation) → stop condition |
| CRIT-004 | HITL routes lack tenant filtering | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1), §164.502) — every endpoint in the namespace needs simultaneous gating; regression coverage requires cross-org fixtures |
| CRIT-005 | Prior-auth tail deletion undetectable | 🔴 HUMAN-REVIEW (CMS-0057-F, HIPAA §164.312(b)) — fix introduces `seq_no` schema change on a tenant-scoped table → stop condition |
| CRIT-006 | Stripe subscription_updated never writes tier | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1)) — affects tier-flip on `/v1/billing/clinic/webhook` → stop condition; plus needs Stripe product-ID-to-tier mapping in CLINIC_TIER_BLUEPRINT §9 |
| CRIT-007 | JWT blacklist not checked in `authenticate_request` | 🔴 HUMAN-REVIEW (HIPAA §164.312(b)) — auth path change; needs distributed Redis blacklist hard dependency (ARCH-FU-7) decided first |
| CRIT-008 | Audit retention deletes without legal-hold | 🔴 HUMAN-REVIEW (HIPAA §164.312(b), §164.530(j)) — adds `legal_hold` column to `audit_logs` (tenant-scoped, audit-log shape) → stop condition |
| CRIT-009 | Migration 006 no-op breaks PostgreSQL roles | New migration required → fits "no new migrations beyond what the fix needs" carve-out, but `ALTER TYPE userrole ADD VALUE` cannot run inside a transaction block; needs deploy-time coordination + rollback plan; deferring to a dedicated DB migration window |
| CRIT-010 | `organization_id` nullable on every tenant table | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1), §164.312(b)); schema mutation across 20+ tenant-scoped tables → stop condition; ARCH-FOLLOWUP-5 (Postgres RLS) |
| CRIT-011 | JWT + User in localStorage | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(2)(i)) — moving to HttpOnly cookies changes the auth contract end-to-end; CSRF middleware revival required |
| CRIT-012 | `/clinic/*` routes lack tier guard at routing layer | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1)) — needs server-side enforcement audit alongside the dashboard change; CRIT-001 tenancy gap must close first |
| CRIT-013 | JWT sent as URL query on WebSocket | 🔴 HUMAN-REVIEW (HIPAA §164.312(e)(2)(i)) — public WebSocket contract change (`/ws/dashboard?token=` → ticket exchange); coordinated client+server release |
| HIGH-001 | Admin shadow-AI cross-tenant listing | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1)) |
| HIGH-002 | HITL POST accepts org_id from body | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1)); paired with CRIT-004 |
| HIGH-003 | Transparency portal endpoints unauthenticated | Public-API shape change to `/v1/transparency` — adding auth changes the contract; needs ONC HTI-1 product decision |
| HIGH-005 | subscription_lifecycle ignores `unpaid` | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1)); requires CRIT-006 tier-write path first |
| HIGH-006 | BAA self-acceptance by any role | 🔴 HUMAN-REVIEW (HIPAA §164.502(e), §164.504(e)) — touches `/v1/clinic/baa/accept`, a `/v1/clinic/*` route → stop condition |
| HIGH-007 | `update_practice` writes phone/address without PHI scan | 🔴 HUMAN-REVIEW (HIPAA §164.530(c)(1)) — touches `/v1/clinic/settings/practice`, a `/v1/clinic/*` route → stop condition |
| HIGH-008 | Scribe-auditor embeds claim text in finding description | 🔴 HUMAN-REVIEW (HIPAA §164.514) — modifies what the auditor persists; PHI invariant requires manual review |
| HIGH-009 | Prior-auth chain ordered by mutable `created_at` | 🔴 HUMAN-REVIEW (HIPAA §164.312(b), CMS-0057-F) — audit-log chain algorithm change → stop condition |
| HIGH-010 | No scheduled prior-auth chain verifier | 🔴 HUMAN-REVIEW (HIPAA §164.312(b)) — scheduler addition coupled to CRIT-005/HIGH-009 |
| HIGH-011 | `hitl_audit_trail.entry_hash` default `''` | 🔴 HUMAN-REVIEW (HIPAA §164.312(b)) — schema change to a tenant-scoped table + audit-log shape → stop condition |
| HIGH-012 | All `DateTime` columns no timezone | 🔴 HUMAN-REVIEW (HIPAA §164.312(b)) — schema change across every tenant-scoped table → stop condition |
| HIGH-013 | Migration 017 silently swallows backfill exception | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1)) — needs production-window re-run plan |
| HIGH-017 | Stripe webhook full-table-scan org resolution | 🏛 ARCH-FOLLOWUP-3 — promotes `stripe_customer_id` out of JSON to an indexed column (schema change to a tenant-scoped table) |
| HIGH-018 | Bias-audit publish gate exception path unimplemented | 🔴 HUMAN-REVIEW (EU AI Act Art.10(4)) — adds new columns to `BiasAuditModel` + new state machine wiring |
| HIGH-019 | Alert acknowledge no comment field | 🔴 HUMAN-REVIEW (HIPAA §164.308(a)(1)(ii)(D)) — schema + API-shape change on `/v1/alerts/{id}/acknowledge` |
| HIGH-020 | HITL SLA wall-clock; escalation_tier never invoked | 🔴 HUMAN-REVIEW (EU AI Act Art.9.7) — needs business-hours/timezone policy + scheduler wiring decision |
| HIGH-021 | Model-card lifecycle: missing REVIEW→DRAFT and PUBLISHED→REVIEW | 🔴 HUMAN-REVIEW (MDR PSUR) — domain state machine change with regulatory implications |
| HIGH-022 | `prior_auth_records` missing composite index | Schema change to a tenant-scoped table → stop condition |
| HIGH-023 | `audit_logs` missing composite index | 🏛 ARCH-FOLLOWUP — schema change to audit-log table → stop condition |
| HIGH-024 | Enterprise routes missing role guards | 🔴 HUMAN-REVIEW (HIPAA §164.312(a)(1)) — broad route-tree change; needs concurrent server-side audit |
| HIGH-028 | ApiClient generic methods typed as `any` | Broad refactor across every HTTP method signature → carve-out for "no refactors"; deferred to a typing-pass branch |
| HIGH-030 | `import.meta` cast to `any` enables BASE_URL hijack | 🔴 HUMAN-REVIEW (HIPAA §164.312(e)(2)(i)) — paired with CRIT-011 / CRIT-013 dashboard auth restructure |

### Verification artefacts

- `git log main..fix/security-and-logic-pass-1 --oneline` → 10 conventional commits
- `bandit -r policy_engine sentinel -ll` → 0 Medium/High findings
- `pytest tests/test_url_validator_ssrf.py tests/test_slack_async_nonblocking.py tests/test_policy_check_failsafe_redaction.py tests/test_transparency_tenant_isolation.py tests/test_migration_005_downgrade.py tests/test_extension_options_validation.py` → 36 passed
- `cd dashboard && npx vitest run src/api/client.test.ts src/types/tier.test.ts src/hooks/useWebSocket.test.tsx src/pages/Dashboard.test.tsx` → 28 passed
- `cd dashboard && npx tsc --noEmit` → 0 errors
- Pre-existing dashboard test failures (12 files / 19 tests) are unrelated to this pass; comparing against pre-branch state shows the resolveTier fix reduces failures from 13 files / 37 tests to 12 / 19.
