# Clinical Shield v1.0 — Construction Plan

> **Generated:** 2026-05-17.
> **Companion to:** `docs/PRD.v2.md` (this plan implements that PRD).
> **Branching:** all v1.0 work lands on a new branch `feat/clinical-shield-v1` cut from `main` (`3ae3f7c`) — **NOT** stacked on `fix/security-and-logic-pass-1`. See §DO-THIS-FIRST.
> **Mode:** branch/PR/CI workflow (git + GitHub CLI present per `git status` on the working tree).
> **Audience:** any coding agent picking up a single phase. Each phase is self-contained — context brief, files touched, verification gates, exit criteria.

---

## Glossary of phases

| Phase | Tier | Workstream | Surface | Independent PR | Risk | Order |
|---|---|---|---|---|---|---|
| **K1** | A | PRD re-affirmation only | `docs/PRD.v2.md` (already written) | yes | Trivial | merge first |
| **A1** | A | AI Tools registry — Model Training Status + Practice Opt-Out State | DB + API + Dashboard | yes | Medium (schema) | parallel-startable |
| **R1** | B | Remove URL-hash pipeline + expand domain list | Extension manifest + `clinic_ai_observations.page_url_hash` deprecation | rolled into the single 0.3.0 store submission with A2+A3 | Low–Medium (write-only field) | rebases onto post-fix `main`; **NOT shipped to public store standalone** |
| **R2** | A | Project clinic UX to Admin/Staff | Dashboard nav + i18n + projection helper | yes | Low (frontend display projection only — no backend RBAC change) | parallel-startable |
| **A2** | B | onBeforePaste hard intercept | Extension content script (all_frames) + new `/v1/clinic/shadow-ai/paste-blocked` endpoint with rate-limit + new `ClinicPasteEvent` model | merged with R1+A3 in single 0.3.0 store submission | **HIGH** — security + healthcare gate | after R1+A3 in same submission |
| **A3** | B | "Sanitize with Sentinel" right-click | Extension content script (shares manifest bump with R1+A2) | merged with R1+A2 in single 0.3.0 store submission | HIGH | with A2 |

K1 is doc-only and merges trivially. A1 and R2 can run in parallel and merge to `main` independently (Tier A). R1, A2, A3 are **collapsed into one extension manifest bump (0.3.0) and one Chrome Web Store / Edge Add-ons submission** — per adversarial review ARCH-3 — and rebase onto post-fix-branch `main` (Tier B). R1 ships to internal testers only as 0.2.0 if at all; the public store sees only 0.3.0.

```
                  K1 (docs · Tier A)
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
      A1 (Tier A)  R2 (Tier A)   R1+A2+A3 (Tier B — single 0.3.0 store submission)
                                  │
                                  └─→ rebase onto post-fix-branch main, then merge
```

---

## DO THIS FIRST

**Branching recommendation (revised after adversarial review — ARCH-1, SEC-1):** start `feat/clinical-shield-v1` off `main` (`3ae3f7c`) **now**, in parallel with the open `fix/security-and-logic-pass-1` Draft PR — but split the v1.0 workstreams into two merge-readiness tiers:

- **Tier A (safe to merge to `main` independently):** K1, A1, R2. These touch `docs/`, `policy_engine/models/clinic.py` (one nullable column), `policy_engine/routes/clinic/tools.py`, and `dashboard/`. Zero overlap with the fix-branch's deferred CRITICAL surfaces.
- **Tier B (must rebase onto post-fix-branch `main`):** R1, A2, A3. These touch `clinic-extension/`, the new `ClinicPasteEvent` table, and `policy_engine/routes/clinic/shadow_ai.py` — exactly the surfaces the fix branch's "stop conditions" lock for tenant-scoped schema, `/v1/clinic/*`, and extension transmit shape. Tier B must not merge to `main` until the fix branch has merged.

Why both tiers exist:

1. The fix branch (`PR_BODY.md:43-55`) explicitly defers **13 CRITICAL + 21 HIGH** findings with stop conditions on the exact surfaces R1/A2/A3 need to touch.
2. The 13 commits already on the fix branch are dashboard + non-clinic backend (Slack, SSRF, transparency tenancy, migration 005, JWT-utils). Zero **file-level** overlap with v1.0 work, but **semantic-level** coupling for R1/A2/A3 (same routes, same models, same extension manifest). Merging R1/A2/A3 first ships v1.0 against a known-vulnerable baseline.
3. K1/A1/R2 have neither file nor semantic coupling with the fix branch and can merge to `main` independently.

**CI enforcement (RR-11):** add a branch-protection rule on `main` that the **Tier B** subset of `feat/clinical-shield-v1` cannot merge while `fix/security-and-logic-pass-1` is still open. Concretely: the v1.0 PR template includes a checkbox "Tier? (A / B)" and a GitHub Action that fails the merge check if Tier is B and the fix-branch PR is not in the merge target's history.

**Merge order at end of v1.0:**

```
main ──────────────────────────────────────────►  (target)
   │
   ├── feat/clinical-shield-v1 (Tier A: K1, A1, R2)  ── merges as ready
   │
   ├── fix/security-and-logic-pass-1                 ── merge when CRITs triaged
   │
   └── feat/clinical-shield-v1 (Tier B: R1, A2, A3)  ── rebases onto post-fix main, then merges
```

**First commit on `feat/clinical-shield-v1`:** the already-written `docs/PRD.v2.md` (workstream K1). That gives every downstream phase a documented spec to point at in the PR body.

---

## Pre-flight checks (run once before phase 1)

```bash
git fetch origin
git switch -c feat/clinical-shield-v1 origin/main    # 3ae3f7c
# untracked PRD.md and REVIEW.*.md are NOT on the fix branch — stash or commit them deliberately;
# they belong on fix/security-and-logic-pass-1, not here.
git stash push -u -m "v1 review docs — fix branch only" -- docs/PRD.md REVIEW.*.md wr.js write_report.js
gh repo view --json defaultBranchRef --jq .defaultBranchRef.name   # expect: main
gh auth status
```

If `gh` is not authenticated, every phase below still produces a local commit; you'll just push and open the PR by hand.

---

## Phase K1 — PRD reframe (already done)

**Status:** `docs/PRD.v2.md` written in this session (the file you are reading next to).

**PR title:** `docs(prd): v1.0 clinical-shield reframe (companion to PRD.md)`

**Acceptance:** docs-only diff, no code, no schema, no CI surface beyond markdown lint.

**Agent ownership:** none — already on disk. Reviewer: `doc-updater` for cross-link integrity check.

---

## Phase A1 — AI Tools Registry: Model Training Status

### A1.0 Cold-start brief

Add a new column `model_training_status` (enum) and `model_training_status_evidence` (free text) to `ClinicAiTool` (`policy_engine/models/clinic.py:52-98`). Surface it in the create/update/response schemas (`policy_engine/routes/clinic/tools.py:39-77`), the dashboard tool list and editor, the monthly compliance PDF (`policy_engine/services/clinic_pdf_report.py:183-237`), and the alert translator with one new alert type (`clinic.tool.trains_on_data`).

The exact UI string (`docs/PRD.v2.md` §6.8.2.b) is locked. The translator copy comes from the gap analysis verbatim.

### A1.1 Files touched

| File | Change |
|---|---|
| `policy_engine/models/clinic.py:52-98` | Add `model_training_status: Enum`, `model_training_status_evidence: String(2000)` |
| `alembic/versions/2026_xx_xx_xxxx-NNN_clinic_model_training_status.py` (new) | Migration on top of head; backfill all rows to `'unknown'` |
| `policy_engine/routes/clinic/tools.py:39-77` | Extend `ToolCreate`, `ToolUpdate`, `ToolResponse` with the two new fields |
| `policy_engine/services/clinic_alert_translator.py` | Add `clinic.tool.trains_on_data` translation |
| `policy_engine/services/clinic_pdf_report.py:75-237` | Aggregate count + new "Tools that train on your data" row |
| `dashboard/src/pages/clinic/ToolList.tsx` | Banner rendering on rows with `trains_on_customer_data` |
| `dashboard/src/pages/clinic/ToolEditor.tsx` | Field UI + helper text + warning banner preview |
| `dashboard/src/i18n/dict/{clinic_basic,clinic_standard,clinic_multi_site}.ts` | Add the four `clinic.tools.training_status.*` keys |
| `dashboard/src/i18n/dict/enterprise.ts` | Fallback keys (English) |
| `tests/clinic/test_routes_tools.py` | New tests for the new field on create/update/list |
| `tests/services_clinic/test_pdf_report_training_row.py` (new) | Assert PDF/HTML output contains the new row when `trains_on_customer_data` rows exist |
| `tests/services_clinic/test_alert_translator_training.py` (new) | Translator output for `clinic.tool.trains_on_data` |

### A1.2 Risk

| Item | Risk | Mitigation |
|---|---|---|
| Alembic migration on `clinic_ai_tools` | **Medium** — tenant-scoped table; partial customer data already exists | Migration adds nullable column with default `'unknown'`; reversible via `op.drop_column`. Round-trip tested locally before merge. |
| Backfill latency | Low | Pure default — no row scan. SQLite + Postgres both O(1) on add-column-with-default for the row count here (single-clinic orgs). |
| Dashboard i18n key churn | Low | New keys only; no rename of existing keys (graceful-degradation rule per `dashboard/src/i18n/provider.tsx:20-27`). |
| Alert fanout (flapping) | Medium | Idempotency window per `docs/PRD.v2.md` §6.8.2.c — flag a tool only once per 30 days. Implemented in the alert dispatch path. |

### A1.3 Test strategy

- **TDD (`superpowers:test-driven-development`):** new tests in `tests/clinic/test_routes_tools.py` + the two new files. RED first, GREEN with minimal patch, REFACTOR.
- **Migration round-trip:** `alembic upgrade head → downgrade -1 → upgrade head` on a copy of the dev DB. New migration file must include a working `downgrade()` (NFR §11 in PRD).
- **Verification gate (`verification-loop` skill):** `pytest tests/clinic tests/services_clinic`, `pytest --cov=policy_engine/routes/clinic --cov=policy_engine/services/clinic_pdf_report --cov-fail-under=85`, `bandit -r policy_engine`, `npx tsc --noEmit`, `npm --prefix dashboard test` (only the touched files).

### A1.4 Agent ownership

| Step | Agent |
|---|---|
| Plan | `planner` (decomposes A1 into the file list above) |
| Schema | `database-reviewer` (migration safety + reversibility) |
| Server code | `python-reviewer` |
| Frontend code | `typescript-reviewer` |
| Copy review | `healthcare-reviewer` (signs off on the exact warning string and on the modernised HIPAA framing) |
| Tests | `tdd-guide` + `e2e-runner` (optional — Playwright through the tool editor) |
| Final gate | `code-reviewer` |

### A1.5 Independence

Independent PR. Does not touch the extension, does not change role hierarchy. Parallel-runnable with R1 and R2.

### A1.6 Exit criteria

- `clinic_ai_tools` row created via `POST /v1/clinic/tools` with `model_training_status='trains_on_customer_data'` renders the locked warning string on the tool list and editor.
- Monthly PDF for an org with at least one such row contains the "Tools that train on your data" line.
- New alert type fires on first flip, suppressed on the second flip within 30 days.
- Coverage ≥ 85% on touched modules. All gates green.

---

## Phase R1 — Strip URL-hash pipeline, expand to ~50 hardcoded domains

### R1.0 Cold-start brief

The current extension SHA-256-hashes the page URL and sends it as `page_url_hash` (`clinic-extension/background.js:34-41,66,78`). The server stores it on `ClinicAiObservation.page_url_hash` (`policy_engine/models/clinic.py:121`) and the dashboard read-side does **not** display it (`policy_engine/routes/clinic/shadow_ai.py:226-236`). The field is write-only — already dead from a product perspective. R1 removes the field from the extension and the Pydantic schema, leaves the DB column in place (nullable) until a follow-up migration drops it after the 30-day backward-compat window.

R1 also expands the hardcoded domain → fingerprint map in `background.js:18-30` from 11 entries to ~50.

### R1.1 Files touched

| File | Change |
|---|---|
| `clinic-extension/background.js:18-30` | Expand `FINGERPRINTS` map to the §5.4.3 list. Severity per tool reviewed by `healthcare-reviewer`. |
| `clinic-extension/background.js:34-41,66,78` | Remove `sha256Hex`, remove `pageUrlHash` from payload. |
| `clinic-extension/manifest.json:5` | Version bump (`0.1.0` → `0.2.0`). |
| `policy_engine/routes/clinic/shadow_ai.py:137-143` | Remove `page_url_hash` from `ObservationCreate` Pydantic schema. **Keep accepting (and ignoring) the field for one quarter** via a feature flag `CLINIC_SHADOW_URL_HASH_ACCEPT` (default ON for now) so old extension versions in the field still POST successfully. |
| `policy_engine/routes/clinic/shadow_ai.py:206-217` | Stop passing `page_url_hash` into the new row even if the field is sent. |
| `tests/factories/clinic.py` | Drop `page_url_hash` from the observation factory. |
| `tests/clinic/test_phase1_smoke.py` | Update assertions. |
| `tests/factories/phi_safe.py` | Drop `page_url_hash` reference. |
| `tests/clinic/test_shadow_ai_url_hash_deprecation.py` (new) | Two tests: (1) extension version 0.1.x payload with `page_url_hash` is accepted (`CLINIC_SHADOW_URL_HASH_ACCEPT=true`), value ignored on insert. (2) Flag off → 422. |
| `docs/USER_MANUAL.md` | Already touched on the working tree (`git status`); confirm copy is consistent with the new domain list. |

### R1.2 Risk

| Item | Risk | Mitigation |
|---|---|---|
| Domain list curation | **Medium** — wrong fingerprint on a major site causes false alerts | `healthcare-reviewer` reviews the final list. Severity defaults to `medium`; only ChatGPT/Claude/Gemini start at `high`. |
| Backward compat with installed extensions | Medium | Feature-flag the server's tolerance of `page_url_hash` for one quarter, then a follow-up migration drops the column. **Not a hard delete in this phase.** |
| Chrome Web Store / Edge re-review | Medium | `host_permissions` narrows from `<all_urls>` to an explicit list. Narrowing permissions usually shortens review; new permissions in A2/A3 will be the harder cycle. R1 alone is a low-risk submission and can ship a version 0.2.0 build to internal testers first. |
| DB column drop | Deferred | Out of scope for R1. Follow-up phase R1-cleanup after 30-day write-rate observation = zero. |

### R1.3 Coupling check (executed during research; documented for the agent)

`grep -r page_url_hash` returns 8 files (per the Grep run on 2026-05-17):

```
REVIEW.security.md                          # documentation only
tests/factories/clinic.py                   # touched
tests/clinic/test_phase1_smoke.py           # touched
tests/factories/phi_safe.py                 # touched
policy_engine/routes/clinic/shadow_ai.py    # touched
policy_engine/models/clinic.py              # column kept for back-compat
alembic/versions/2024_02_23_0000-016_clinic_tier.py   # migration, untouched
clinic-extension/background.js              # touched
```

**No production reader.** The only consumers are the writer (`shadow_ai.py:211`) and the factory used in tests. Safe to delete with a feature-flag fallback for installed clients.

### R1.4 Test strategy

- TDD on the new deprecation test.
- Regression suite: `pytest tests/clinic tests/factories`, then `pytest tests/test_phi_scan_meta.py tests/test_extension_manifest.py` (the manifest-hygiene scan from PR_BODY tests — must still pass).
- Manual: load the unpacked extension into Chrome, point at a curated test URL list of ~10 of the 50 tools, observe observations posted with the new shape.
- Verification gate: `pytest -m clinic`, `npx eslint clinic-extension/`, bandit on `policy_engine/routes/clinic/`.

### R1.5 Agent ownership

| Step | Agent |
|---|---|
| Plan | `planner` |
| Extension JS | `typescript-reviewer` (works on `.js` too) |
| Server schema | `python-reviewer` |
| Domain list curation | `healthcare-reviewer` (which AI tools are actually used in US clinics) |
| Security cross-check | `security-reviewer` (manifest permission narrowing) |
| Tests | `tdd-guide` |
| Final gate | `code-reviewer` |

### R1.6 Independence

Independent PR; parallel-runnable with A1 and R2. **Blocks** A2 (must land first so the manifest bump for A2 is incremental, not a double change).

### R1.7 Exit criteria

- Extension 0.2.0 built locally, manifest validates with new domain list and without `webRequest` no longer in the permissions array.
- `POST /v1/clinic/shadow-ai/observations` accepts payloads without `page_url_hash`; backward-compat test passes.
- All clinic + factory tests green.
- Coverage on touched modules ≥ 85%.

---

## Phase R2 — Collapse clinic UX to Admin + Staff

### R2.0 Cold-start brief

Today the dashboard exposes 8 backend roles end-to-end (`policy_engine/models/user.py:10-20`, `dashboard/src/types/index.ts:5-14`, `dashboard/src/config/navigation.ts:60`). The product reframe (`docs/PRD.v2.md` §3.1) needs a two-role projection for clinic-tier UX only. **The backend enum is not removed** — that's the entire reversibility story.

The change is a thin projection layer:

- New helper `getClinicProductRole(user) -> 'admin' | 'staff'` in `dashboard/src/auth/clinicProductRole.ts` (new file).
- `NAV_SECTIONS` for clinic tiers (`dashboard/src/config/navigation.ts:33-66`) uses the projected role instead of the canonical 8-role enum.
- Practice Settings (`navigation.ts:60`) stays restricted to `[SYSTEM_ADMIN, ADMIN, COMPLIANCE_OFFICER]` *server-side*, but in the projection layer only `admin` (= product Admin) sees the link.
- i18n key renames in the three clinic dicts: `clinic.role.cmio` → not used, replaced with `clinic.role.staff` for any view rendering the user role.
- **Zero backend changes.** `policy_engine/auth/rbac.py`, `policy_engine/models/user.py:56-163` (`ROLE_PERMISSIONS`), and the rest of the API surface are untouched.

### R2.1 Files touched

| File | Change |
|---|---|
| `dashboard/src/auth/clinicProductRole.ts` (new) | Pure function: `(user, tier) → 'admin' \| 'staff'`. `system_admin` and `admin` → `'admin'` on clinic tiers; everyone else → `'staff'`. On enterprise tier, returns the canonical role unchanged. |
| `dashboard/src/config/navigation.ts:33-66` | Use the projection. `Practice Settings.allowedRoles` switches from `[SYSTEM_ADMIN, ADMIN, COMPLIANCE_OFFICER]` to the product-role check on clinic tiers. Enterprise sections (`navigation.ts:69+`) untouched. |
| `dashboard/src/contexts/AuthContext.tsx` | Surface `productRole` alongside `role` for clinic-tier renders. |
| `dashboard/src/components/layout/AppLayout.tsx` | Render the friendly product role in the user menu on clinic tiers. |
| `dashboard/src/i18n/dict/clinic_basic.ts` (+ standard, multi_site) | Add `clinic.role.admin`, `clinic.role.staff`. Keep existing 8-role keys for graceful degradation. |
| `dashboard/src/auth/__tests__/clinicProductRole.test.ts` (new) | Property test: every 8-role × 4-tier combination produces the expected projection. |
| `dashboard/src/config/__tests__/navigation.test.ts` | Update fixture — clinic-tier nav for a `cmio` user now matches `staff`. |
| `policy_engine/models/organization.py:14-19` | **No change.** `OrgType` enum is left alone. (Workstream R2 is **not** the hospital-tier migration — it's a UX projection.) |
| `policy_engine/auth/rbac.py` | **No change.** Still enforces the canonical 8-role permissions. |
| `policy_engine/models/user.py` | **No change.** |

### R2.2 Risk

| Item | Risk | Mitigation |
|---|---|---|
| **Destructive Alembic migration?** | **None.** R2 has no migration. The backend enum stays. | Documented refusal: R2 does not touch `User.role` schema. |
| RBAC regression | Medium | The projection is a frontend-only restriction layered on top of the canonical RBAC. Server-side enforcement is unchanged (`rbac.py` + `ROLE_PERMISSIONS` cover the actual access decision). A clinical_user on a clinic tier with a forged JWT still gets the same `403`s server-side as today. |
| Future hospital-persona path | Locked in | The projection is `if isClinicTier(tier) { ... } else { return canonicalRole }`. To add a future hospital persona, swap the projection — no enum change needed. |
| i18n bundle bloat | Low | New keys are small (<200 bytes per dict). NFR §11 ceiling (50 KB gzipped for `clinic_basic`) untouched. |

### R2.3 Test strategy

- TDD on `clinicProductRole.test.ts` first.
- Update existing `navigation.test.ts` fixtures.
- Add a regression: server-side request with a `cmio` JWT to `/v1/clinic/settings/practice` still works (`cmio` is not in `[ADMIN, COMPLIANCE_OFFICER]` per `routes/clinic/settings.py` — confirm against the current 403 behaviour, do not change it).
- Verification: `npx vitest run dashboard/src`, `pytest tests/test_rbac.py` (sanity-check no regression).

### R2.4 Agent ownership

| Step | Agent |
|---|---|
| Plan | `planner` |
| Frontend code | `typescript-reviewer` |
| Tests | `tdd-guide` |
| RBAC regression sanity | `security-reviewer` |
| Final gate | `code-reviewer` |

### R2.5 Independence

Independent PR; parallel-runnable with A1 and R1. No backend coupling.

### R2.6 Exit criteria

- A `cmio` user on a `clinic_basic` org sees the staff nav (no Practice Settings link); same user on an `enterprise` org sees the full CMIO nav. Unit test asserts both.
- No backend route returns a different status code than it does today on the same JWT.
- Server-side `ROLE_PERMISSIONS` diff is zero lines.

---

## Phase A2 — onBeforePaste hard intercept (highest-stakes change)

### A2.0 Cold-start brief

This is the workstream that turns Sentinel from a telemetry product into a prevention product. The contract (`docs/PRD.v2.md` §6.8.7): on a tab whose host matches the §5.4.3 allowlist, intercept the `paste` event in a content script with `capture: true`, run local PHI regex, block with a Shadow-DOM modal if any pattern matches, optionally allow an override (audit-logged), and never transmit the paste contents.

A2 ships **stacked with A3** in the same extension manifest bump (single Chrome Web Store / Edge Add-ons submission — two reviews in one window).

A2 **MUST** have `security-reviewer` and `healthcare-reviewer` sign-off as a hard gate before the PR can merge.

### A2.1 Files touched

| File | Change |
|---|---|
| `clinic-extension/content.js` (new) | Paste interceptor + override modal (Shadow DOM). |
| `clinic-extension/phi_patterns.js` (new) | Client-side mirror of `policy_engine/services/phi_text_check.py:26-58` + NPI + ICD-10 patterns. Exported for re-use by A3. |
| `clinic-extension/background.js` | On `chrome.tabs.onUpdated`, if `host` matches allowlist, `chrome.scripting.executeScript({ files: ['content.js'] })`. |
| `clinic-extension/manifest.json` | Bump to `0.3.0`. Add `scripting`. Add `contextMenus` (consumed in A3). Add `clipboardWrite`. Narrow `host_permissions` to the §5.4.3 list (was `<all_urls>`). |
| `policy_engine/models/clinic.py` | Add `ClinicPasteEvent` table (`id`, `org_id`, `host`, `tool_fingerprint`, `action`, `observed_at`, `user_agent`, `extension_version`). Index `(org_id, observed_at desc)`. |
| `alembic/versions/2026_xx_xx_xxxx-NNN_clinic_paste_events.py` (new) | Migration for the new table. |
| `policy_engine/routes/clinic/shadow_ai.py` | Add `POST /v1/clinic/shadow-ai/paste-blocked` handler. Same hashed-token auth as the existing observations endpoint (`shadow_ai.py:146-221`). Same BAA-required gate. |
| `policy_engine/services/clinic_alert_translator.py` | Add `clinic.paste.blocked`, `clinic.paste.override` translation copy (per `docs/PRD.v2.md` §6.1.5.a). |
| `tests/clinic/test_paste_blocked_endpoint.py` (new) | Server-side tests: auth, BAA gate, tenant scoping, payload validation. |
| `tests/clinic/test_phi_patterns_client_mirror.py` (new) | Asserts the client-side patterns return identical match sets to the server-side regex for a shared corpus. |
| `clinic-extension/__tests__/content.test.js` (new, vitest + jsdom) | Simulates paste events; asserts `preventDefault` called, modal injected, telemetry POSTed with no content. |

### A2.2 Risk

| Item | Risk | Mitigation |
|---|---|---|
| **PHI false-negative on the paste blocker = breach** | **CRITICAL** | Hard eval gate: synthetic PHI corpus + synthetic non-PHI corpus, false-negative rate < 1% on PHI, false-positive rate < 5% on non-PHI. Corpus seeded by `healthcare-reviewer`; HIPAA-realistic but never real PHI. The gate **blocks merge.** |
| Chrome Web Store re-review | **High** | New permissions (`scripting`, `contextMenus`, `clipboardWrite`) require justification. Submit A2+A3 together to amortise one review cycle. Pre-discuss with the extension store via the developer support channel **before** code freeze if possible. Budget 5–10 business days from submission to publish. |
| Race condition with the AI tab's own paste handler | High | `capture: true` + `stopImmediatePropagation`. Verified by an integration test using Playwright. |
| Override fatigue (staff click through every block) | Medium (product) | Audit the override rate in the next monthly PDF (A1's report extension). If overrides > 50% of blocks, raise a `clinic.paste.override_rate_high` alert in v1.1. |
| Tenant-scoped table addition vs. fix-branch stop conditions | None **for this branch** — see DO-THIS-FIRST. | Branch is off main; not stacked on the fix branch. |
| Modal injected into a third-party page (CSP, iframe edges) | Medium | Shadow-DOM root attached to `document.documentElement`, not `body`. Inline styles only (CSP-safe). Tested on the top-3 AI tools' actual DOMs. |

### A2.3 Test strategy

- **TDD via `superpowers:test-driven-development`** on every new file.
- Eval harness (NEW): `clinic-extension/__evals__/phi_corpus.json` (synthetic), `__evals__/non_phi_corpus.json`. Run via vitest with `--reporter=verbose`; fail the run if rates exceed the gate.
- Integration via Playwright (`@playwright/test` is already a devDep per `PR_BODY.md:73`): paste into a mock AI tab page, assert the underlying input never receives the keystroke event.
- Verification loop (`verification-loop` skill): `pytest tests/clinic`, `npx vitest run clinic-extension/`, `npx playwright test e2e/paste-block.spec.ts` (new). `bandit -r policy_engine/routes/clinic`.

### A2.4 Agent ownership — **gate**

| Step | Agent | Gate |
|---|---|---|
| Plan | `planner` | — |
| Architect review (paste-event contract) | `architect` | required before code |
| Extension JS | `typescript-reviewer` | — |
| Server schema | `database-reviewer` | required (new tenant-scoped table) |
| Server code | `python-reviewer` | — |
| **Security sign-off** | `security-reviewer` | **HARD GATE** |
| **Healthcare sign-off (PHI eval corpus + breach posture)** | `healthcare-reviewer` | **HARD GATE** |
| Tests | `tdd-guide` + `e2e-runner` | required (Playwright spec) |
| Final gate | `code-reviewer` | — |

Both `security-reviewer` and `healthcare-reviewer` must approve in writing (PR review with "Approve" verdict). A `Block` from either auto-blocks merge.

### A2.5 Independence

**Stacked with A3** — same extension manifest, same store submission. PR can be opened independently but cannot merge before A3 is also reviewed; the store submission goes out as one build.

Depends on R1 (manifest bump and domain-list narrowing should have shipped to the extension store first so A2's manifest delta is purely additive on permissions).

### A2.6 Exit criteria

- Eval gates green: < 1% FN on PHI corpus, < 5% FP on non-PHI corpus.
- Playwright integration test: paste with PHI on a mock AI tab, target input is empty.
- `POST /v1/clinic/shadow-ai/paste-blocked` returns `202` on a valid token, `401` on a wrong token, `409` when BAA not signed (mirroring `routes/clinic/shadow_ai.py:186-199`).
- New alert type `clinic.paste.blocked` renders the locked translator copy.
- security-reviewer + healthcare-reviewer reviews recorded on the PR.

---

## Phase A3 — Sanitize with Sentinel (right-click context menu)

### A3.0 Cold-start brief

Right-click selection → "Sanitize with Sentinel" → local transformation → clipboard. Original text never leaves the browser process (`docs/PRD.v2.md` §6.8.9). Shares the manifest bump with A2.

### A3.1 Files touched

| File | Change |
|---|---|
| `clinic-extension/background.js` | Register `chrome.contextMenus.create({ id: 'sentinel-sanitize', contexts: ['selection'] })`. Forward click to content script. |
| `clinic-extension/content.js` (added in A2; A3 extends) | Handler for the menu click: read selection, apply transformations, `navigator.clipboard.writeText`, toast. |
| `clinic-extension/sanitize.js` (new) | Pure transformation module. Imports `phi_patterns.js` from A2. Returns `{ sanitized: string, replacementMap: Record<string, string> }`. |
| `clinic-extension/__tests__/sanitize.test.js` (new) | Idempotency, replacement-token uniqueness, name heuristic spot-checks. |
| `policy_engine/services/clinic_alert_translator.py` | Add `clinic.sanitize.used` copy. |
| No new server endpoint | Reuse `POST /v1/clinic/shadow-ai/paste-blocked` with `action: 'sanitize_used'` (A2's endpoint already takes the field). |

### A3.2 Risk

| Item | Risk | Mitigation |
|---|---|---|
| Patient-name heuristic (capitalised tokens) | **High false-negative risk** | UX side: a confirmation toast says "We replaced N identifiers — review before pasting." Off-loads residual risk to the user. Same eval corpus as A2 — the sanitiser must produce **zero plaintext PHI** for any PHI-corpus input; failure-to-sanitise (i.e., the output still contains an identifier) is a HARD merge gate. |
| Extension bundle size | Low | Regex-only. < 5 KB additional. |
| Store re-review | Same as A2 — co-submitted. |
| Race condition with the AI tab's own context menu | Low | The Chrome `contextMenus` API runs above page content menus by default. |

### A3.3 Test strategy

- TDD on `sanitize.test.js`.
- Eval gate: PHI corpus from A2, asserts **no** identifier in the post-sanitisation output for any input. False-positive rate (over-redaction) is acceptable; false-negative is not.
- Manual: right-click on a real (synthetic) PHI string, paste into ChatGPT — verify clipboard contents.

### A3.4 Agent ownership

| Step | Agent | Gate |
|---|---|---|
| Plan | `planner` | — |
| Implementation | `typescript-reviewer` | — |
| **Security sign-off** | `security-reviewer` | **HARD GATE** (because original text could leak if the implementation mis-handles the clipboard) |
| **Healthcare sign-off** | `healthcare-reviewer` | **HARD GATE** |
| Tests | `tdd-guide` | — |
| Final gate | `code-reviewer` | — |

### A3.5 Independence

**Stacked with A2** in a single PR (or two PRs that target the same merge train). Same extension manifest.

### A3.6 Exit criteria

- Right-clicking selected text → menu item appears.
- Click → clipboard contains transformed text; original DOM selection unchanged.
- Eval gate green (zero PHI identifiers in sanitised output).
- `clinic.sanitize.used` alert renders the locked translator copy.

---

## Risk register (cross-phase)

| ID | Risk | Phase(s) | Owner | Status |
|---|---|---|---|---|
| **RR-1** | Is the URL-hash pipeline load-bearing for any other feature? | R1 | `architect` | **Investigated 2026-05-17.** Grep on `page_url_hash` returns 8 files; zero production readers. The dashboard's `ObservationResponse` schema (`policy_engine/routes/clinic/shadow_ai.py:226-236`) does not include the field. Safe to deprecate behind a server-side accept-but-ignore flag, then drop the column. **Decision: feature-flag (not hard delete) for R1; column drop deferred to R1-cleanup. Window shortened to 30 days per ARCH-4.** |
| **RR-2** | Does collapsing the org model require a destructive Alembic migration? | R2 | `architect` + `database-reviewer` | **Avoided by design.** R2 is a frontend-only projection layer. Backend `UserRole` enum and `ROLE_PERMISSIONS` dict stay unchanged. Future hospital persona is a projection swap, not a migration. **No Alembic migration needed for R2.** |
| **RR-3** | Chrome Web Store / Edge Add-ons re-review for new permissions | R1 + A2 + A3 | `security-reviewer` | R1+A2+A3 submitted as **one** extension build (manifest 0.3.0). Permissions added: `scripting`, `contextMenus`, `clipboardWrite`. `webRequest` removed (R1). `host_permissions` narrowed from `<all_urls>` to an explicit allowlist (R1). R1 stays internal-testers-only if standalone (per ARCH-3). Calendar risk: 5–10 business days; does not block Tier A workstreams. |
| **RR-4** | PHI false-negative on the paste blocker = HIPAA breach | A2 | `healthcare-reviewer` + `security-reviewer` | Hard eval gate split (per HEALTH-1): FN < 1% on the **structured-PHI** sub-corpus; narrative-PHI sub-corpus reported separately and disclosed in §10.2.d, not gated. Corpus seeded from a published synthetic dataset (MITRE/synthea) plus `healthcare-reviewer` additions; second reviewer required on the corpus itself (ARCH-6). |
| **RR-5** | Sanitiser fails to redact a patient name = HIPAA breach | A3 | `healthcare-reviewer` | Gate rewritten (HEALTH-7): zero leakage of **structured** identifier categories. Names / addresses are not gated; toast copy explicitly disclaims that "names and addresses are NOT automatically detected." |
| **RR-6** | Schema additions on tenant-scoped tables collide with fix branch's deferred CRITICAL stop conditions | A1 + A2 | DO-THIS-FIRST | Resolved by Tier A / Tier B split (per ARCH-1 + SEC-1). A1 is Tier A (one nullable column, no overlap with fix-branch CRITICALs). A2's new `ClinicPasteEvent` table is Tier B and rebases onto post-fix `main`. |
| **RR-7** | Alembic migration reversibility | A1 + A2 | `database-reviewer` | Every new migration must include a working `downgrade()` that round-trips. NFR §11 (PRD §11) preserved. |
| **RR-8** | Backwards-compat for old extension versions still in the field | R1 | `architect` | `CLINIC_SHADOW_URL_HASH_ACCEPT` feature flag on the server, default ON. **Window: 30 days** (was one quarter — ARCH-4). After 30 days with zero new writes of `page_url_hash`, R1-cleanup drops the column. Accept-path validates value against `^[a-f0-9]{1,128}$` to block log injection (SEC-6). |
| **RR-9** | Extension store + content-script CSP edge cases on the top AI tools | A2 + A3 | `e2e-runner` | Smoke-test the top 3 sites (ChatGPT, Claude, Gemini) end-to-end in Playwright before submitting to the store. **Test must include an iframe paste target** per SEC-2. |
| **RR-10** | Override fatigue (staff click through every paste block) | A2 (post-launch) | product (out of scope for v1.0) | Tracked via the new `clinic.paste.override` audit. v1.1 alert if override rate > 50%. |
| **RR-11** | v1.0 Tier B merges to `main` before the fix branch lands → ships against a known-vulnerable baseline | meta | `security-reviewer` | CI rule on the `feat/clinical-shield-v1` Tier-B PR template: GitHub Action checks that `fix/security-and-logic-pass-1` is in the merge-target history before allowing merge. Added per SEC-1. |
| **RR-12** | Replay-poisoning the new `/paste-blocked` endpoint to forge audit overrides | A2 | `security-reviewer` | Endpoint rate-limited at 60 events per token per minute. Insert-time dedup on `(org_id, host, action, regex_categories_matched, observed_at` rounded to 1 s`)`. Added per SEC-4. |
| **RR-13** | Extension auto-update or compromised publisher account → supply-chain compromise | A2 + A3 (post-launch) | `security-reviewer` | Document the publishing pipeline access-control matrix (who can push to Chrome Web Store / Edge Add-ons developer accounts). Enable 2FA + push-protection on the publisher account. Audit log every store-side publish event. SHA-pin the extension build in `docs/PRD.v2.md` §5.4.4 already exists. Added per SEC-missing-1 (OWASP A08). |
| **RR-14** | `ClinicPasteEvent` aggregate-inference: per-row data is non-PHI, but a small clinic's row pattern can de-anonymise patient encounters | A2 (post-launch) | `healthcare-reviewer` | Documented in PRD §10.2.b. Retention sweep (`clinic_retention_sweep`) extended to roll `ClinicPasteEvent` rows older than 90 days into per-day aggregates (no per-event row, per-day count only). Added per SEC-missing-2. |
| **RR-15** | Chrome Web Store / Edge Add-ons policy may reject paste-event interception as a "single-purpose" / clipboard-policy violation regardless of HIPAA framing | A2 + A3 | `security-reviewer` + product | Submit a policy pre-discussion to the Chrome Web Store developer support channel **before** code freeze. Have a written "single purpose: HIPAA-compliant paste prevention for clinical staff" justification ready, with HIPAA citations. If rejected outright, fall back to a Manifest V3 enterprise-deployment-only distribution (corporate policy install). Added per SEC-missing-3. |
| **RR-16** | Local-only operating mode (BAA not signed) leaves practice with a paste-blocker but **no server audit trail**, which is worse than no tool installed for §164.312(b) | A2 | `healthcare-reviewer` | Plan changed per HEALTH-4: extension refuses to enable on allowlisted domains until a BAA endpoint returns 200; until then the dashboard displays a persistent banner *"Sentinel is not protecting your practice yet — sign your BAA in Compliance Settings."* No silent local-only state. |
| **RR-17** | UI projection in R2 silently shows empty data pages to roles that map to `staff` but have different server-side access | R2 | `security-reviewer` | Per SEC-7 + ARCH-2: enumerate the role-to-route access matrix in the R2 PR body. Nav shows the **intersection** of accessible routes for all roles that project to `staff`, OR displays a clear "access denied" state — not a silently empty data view. Test `tests/test_rbac.py` confirms server-side RBAC is unchanged. |

---

## Verification matrix

| Phase | TDD | Verification gate (skill: `verification-loop`) | Eval gate | Store review |
|---|---|---|---|---|
| K1 | n/a | markdown lint | — | — |
| A1 | yes | pytest + bandit + tsc + vitest + alembic round-trip | — | — |
| R1 | yes | pytest + eslint + bandit + manual unpacked-load | — | yes (low risk) |
| R2 | yes | vitest + pytest (RBAC regression sanity) | — | — |
| A2 | yes | pytest + bandit + alembic round-trip + vitest + playwright | **HARD** (FN < 1%, FP < 5%) | yes (stacked with A3) |
| A3 | yes | vitest + playwright + manual | **HARD** (zero PHI leak) | yes (stacked with A2) |

---

## Plan-mutation log

Tracks any structural change to this plan after it's been used. Update on every split/insert/skip/reorder/abandon.

| Date | Phase | Mutation | Reason |
|---|---|---|---|
| 2026-05-17 | — | Plan created | Initial draft. |
| 2026-05-17 | DO-THIS-FIRST, glossary, RR-* | Tier A / Tier B split; CI merge-gate added; R1+A2+A3 collapsed into one extension submission; risk register expanded RR-11..RR-17 | Adversarial review by `architect`, `security-reviewer`, `healthcare-reviewer` (see Adversarial-review log below). |
| 2026-05-17 | DO-THIS-FIRST, RR-6, RR-11 | **`fix/security-and-logic-pass-1` merged to `origin/main` as PR #1 (`e9e4a2e`) — discovered during execution kick-off.** Tier A/B merge-order ordering is moot (no waiting needed). RR-11 CI gate is mechanically moot. Underlying vulnerable-baseline concern unchanged: the 13 deferred CRITICALs are now part of main as deferred items, not fixed. Tier-B work still requires per-PR human review against the deferred-CRITICAL list before touching the same surfaces — but no longer needs branch-order enforcement. `feat/clinical-shield-v1` cuts from `origin/main` at `e9e4a2e`. | Live state diverged from the plan's assumed branch state. |
| 2026-05-18 | R2, RR-17 | **R2 landed; access matrix recorded in R2-PLAN.md.** Frontend-only product-role projection helper (`dashboard/src/auth/clinicProductRole.ts`) + Practice-Settings nav gate (`allowedProductRoles: ['admin']`) + AuthContext `productRole` + clinic.role.{admin,staff} i18n keys (en + es) + backend RBAC snapshot guard (`tests/test_r2_no_backend_change.py`, SHA-256 + ROLE_PERMISSIONS deep-equal). Backend `policy_engine/auth/rbac.py` and `policy_engine/models/user.py` untouched. Deviation from R2-PLAN task #9: did not extend `tests/test_rbac.py` with the 8-role × clinic-route parametrise, per dispatcher constraint forbidding test-file edits beyond the new snapshot guard. Existing `test_rbac.py` still runs unchanged and green. | R2 plan executed; one task deferred per dispatcher constraint. |

---

## Adversarial-review log

Every finding from the three reviewers is recorded here. Findings that did not change the plan body are still listed so the executing phase agent inherits the context. Anchors below are referenced by ID throughout the plan and the PRD.

### Architect findings (`architect`)

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| **ARCH-1** | HIGH | "Off main, not stacked on fix branch" claim relies on file-level grep. Semantic coupling exists (same routes, same models). | Tier A/B split. Tier B rebases onto post-fix main. See DO-THIS-FIRST. |
| **ARCH-2** | MEDIUM | R2 projection layer turns `Practice Settings.allowedRoles` into an authz decision in nav config — two sources of truth with backend RBAC. | Plan §R2 + RR-17: enumerate access matrix in PR body; nav uses intersection of accessible routes or explicit access-denied state. |
| **ARCH-3** | HIGH | A2+A3 single-store-submission depends on whether R1 publishes to the public store standalone. | R1 stays internal-testers-only; one public 0.3.0 submission contains R1+A2+A3. Glossary + diagram updated. |
| **ARCH-4** | MEDIUM | R1 feature-flag default ON for one quarter is too long for a write-only field. | Window shortened to 30 days. RR-8 updated. |
| **ARCH-5** | MEDIUM | PHI client/server pattern mirror drifts if hand-duplicated. | Single source of truth: `policy_engine/services/phi_patterns.json` generates both sides at build time. NPI + ICD-10 added to server side in the same PR. PRD §6.8.7.a updated. |
| **ARCH-6** | LOW | Eval corpus seeded by a single reviewer is a tautological gate. | Corpus seeded from a published synthetic dataset (MITRE/synthea) plus reviewer additions; second reviewer required on the corpus itself. A2.4 updated. |

### Security findings (`security-reviewer`)

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| **SEC-1** | CRITICAL | No hard gate prevents v1.0 from merging to `main` before the fix branch lands. | CI rule + Tier A/B split + RR-11. |
| **SEC-2** | HIGH | `stopImmediatePropagation` on top-frame `document` is bypassed when AI tab renders its input in an iframe. | `all_frames: true` on content-script injection. PRD §6.8.7.a + §6.8.7.c iframe test. |
| **SEC-3** | HIGH | `navigator.clipboard.writeText('')` fails silently under Permissions-Policy gates → product claim "we cleared your clipboard" is false. | Two-step path: synchronous `execCommand('copy')` against hidden empty textarea primary, `writeText` fallback with caught rejection + user-visible note. PRD §6.8.7.a + §6.8.7.e. |
| **SEC-4** | HIGH | New `/paste-blocked` endpoint lacks rate-limit / anti-replay; a stolen extension token can forge audit overrides. | 60 events / token / min rate limit; insert-time dedup; PRD §6.8.7.b; RR-12. |
| **SEC-5** | HIGH | PHI regex set missing 3+ HIPAA Safe Harbor identifiers (ZIP, IP, insurance-ID, etc.). | Added in v1.0 to both client and server. PRD §6.8.7.a + §6.8.7.d gap table. |
| **SEC-6** | MEDIUM | R1 accept-path is a log-injection vector if `page_url_hash` is logged. | Strict validator `^[a-f0-9]{1,128}$` at Pydantic level before any log path. RR-8 updated. |
| **SEC-7** | MEDIUM | R2 projection shows empty data pages to demoted-but-still-have-some-access roles → false compliance attestation. | Per-role access matrix documented; nav shows intersection or explicit denied. RR-17. |
| **SEC-8** | MEDIUM | A3 clipboard-write sequencing vs. malicious page `oncopy` overrides. | Documented as residual risk: malicious page is orthogonal to the PHI protection goal — a malicious page already has page-context clipboard access. A3.2 risk row. |
| **SEC-missing-1** | MEDIUM | OWASP A08 — extension auto-update / publisher-account supply-chain risk not in register. | RR-13 added. |
| **SEC-missing-2** | MEDIUM | `ClinicPasteEvent` aggregate-inference risk under HIPAA §164.502 not analysed. | RR-14 added + retention sweep extended. |
| **SEC-missing-3** | HIGH | Chrome Web Store / Edge Add-ons policy may reject paste interception under "single-purpose" / clipboard rules. | RR-15 added + pre-submission policy discussion mandated. |

### Healthcare findings (`healthcare-reviewer`)

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| **HEALTH-1** | CRITICAL | Safe-Harbor coverage gap vs. "PHI never leaves the device" sales claim. Regex catches structured identifiers but misses names, narrative dates, addresses, etc. | PRD §4.1.1 demoted to "structured PHI identifiers are blocked at the device"; §10.2.d narrowed; §6.8.7.d disclosure table; A2 eval gate split (structured FN < 1% gated; narrative FN reported separately). |
| **HEALTH-2** | CRITICAL | Locked warning string is legally overreaching ("permanently leaked to the public domain"), BAA-blind, English-only. | Rewritten as BAA-aware bilingual copy. PRD §6.8.2.b. Spanish translation a v1.0 gate. |
| **HEALTH-3** | HIGH | Override audit captures no content → can't reconstruct a breach under 45 CFR §164.312(b). | Audit captures `regex_categories_matched` (category names, not content). PRD §6.8.7.a step 6 + §6.8.7.c. Trade-off documented. |
| **HEALTH-4** | HIGH | Local-only mode (BAA not signed) is worse than not deploying — practice believes it's protected but has no audit trail. | Extension refuses to enable until BAA signed; dashboard banner makes the state explicit. RR-16. |
| **HEALTH-5** | HIGH | `opt_out_available` records vendor capability, not practice configuration — not auditable. | Split into `model_training_status` + `practice_opt_out_state` + `opt_out_verified_at/by`. PRD §6.8.2.a. Only Admin (product role) can mark Verified. |
| **HEALTH-6** | MEDIUM | NPI Luhn pattern wrong without the CMS `80840` prefix. | Algorithm quoted verbatim in `phi_patterns.json`; unit test with CMS doc example `1234567893`. PRD §6.8.7.a. |
| **HEALTH-7** | MEDIUM | A3 gate "zero plaintext PHI" is unachievable with regex + capitalisation; either implementation silently relaxes or A3 never merges. | Gate rewritten: "zero leakage of structured identifier categories"; toast disclaims names/addresses. PRD §6.8.9.c. RR-5 updated. |
| **HEALTH-8** | MEDIUM | DOB regex misses 2-digit-year notation (`03/14/58`). | 2-digit-year variant added, gated on `DOB|dob|born|d\.o\.b` left-context anchor. PRD §6.8.7.a. |

### Verdict

The reviewers agreed the plan is **structurally sound** (branching strategy, gate discipline, TDD posture) but rejected three load-bearing claims as written:

1. The "PHI never leaves the device" headline (HEALTH-1 / SEC-5) — now narrowed to structured identifiers with explicit gap disclosure.
2. The locked warning copy (HEALTH-2) — now BAA-aware + bilingual.
3. The "off-main-not-stacked" branching call (ARCH-1 / SEC-1) — now Tier A / Tier B split with a CI merge gate.

Every other finding is captured in the risk register (RR-11 through RR-17) or in the corresponding PRD section. No finding is unresolved.

---

*End of plan.*
