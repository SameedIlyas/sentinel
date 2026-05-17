# R2-PLAN.md — Workstream R2: Collapse clinic UX to Admin + Staff

> Phase-specific executable plan for workstream R2 of `plans/clinical-shield-v1.md`. Authored by `planner` agent under adversarial-review constraints (ARCH-2, SEC-7, RR-17).
> Tier A. Independent PR. Frontend-only — zero backend changes.

## Overview

Add a thin frontend-only projection layer that renders eight backend roles as two product roles (`admin` / `staff`) on clinic tiers. Backend RBAC, the `UserRole` enum, and `ROLE_PERMISSIONS` (`policy_engine/models/user.py:10-20,56-163`) are untouched.

## Critical access-matrix finding (RR-17)

**Discovered during plan research**: grep across `policy_engine/routes/clinic/` for `require_role`, `require_permission`, or `has_permission` returns **zero matches**. Every clinic route uses only:

- `Depends(get_current_user)` (`policy_engine/auth/rbac.py:19-76`)
- `Depends(require_clinic_tier)` (`policy_engine/services/tier_filter.py:54-68`)
- Optionally `Depends(require_clinic_tier_with_baa)` (`tier_filter.py:71-95`)

There is **no role check** on any `/v1/clinic/*` route today. On a clinic-tier org, every authenticated active user reaches every clinic route with HTTP 200 regardless of `UserRole`. The only gates are: (a) clinic tier present, (b) BAA signed for PHI-write paths, (c) extension-token auth for `POST /shadow-ai/observations`.

**Implication**: the RR-17 "silent empty page" risk reduces to: a `staff`-projected user direct-navigating to `/clinic/settings/practice` still gets a 200 + working page from the server. We resolve this by hiding only the nav link — server still grants direct access. **No "access denied" state is required** for R2.

## Role × clinic-route access matrix

All rows derived from `policy_engine/auth/rbac.py:19-76`, `tier_filter.py:54-95`, and each `routes/clinic/*.py` dependency list. Assumes `is_active=True`, `organization_id` set, org `tier ∈ CLINIC_TIERS`.

`*` = 200 when `Organization.hipaa_baa_signed=True`; otherwise 403 `baa_required` (from `require_clinic_tier_with_baa`, `tier_filter.py:82-94`).

| Backend role | `/dashboard/summary` | `/tools` GET | `/tools` POST | `/policy-templates` GET | `/policy-templates/apply` | `/alerts` GET | `/reports` GET | `/reports/generate` | `/shadow-ai/observations` GET | `/shadow-ai/extension-token` POST | `/onboarding` GET | `/settings/practice` GET/PUT | `/settings/plan` GET | `/baa/status` | `/baa/accept` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `system_admin` | 200 | 200 | 200* | 200 | 200* | 200 | 200 | 200* | 200 | 200 | 200 | 200 | 200 | 200 | 200* |
| `admin` | 200 | 200 | 200* | 200 | 200* | 200 | 200 | 200* | 200 | 200 | 200 | 200 | 200 | 200 | 200* |
| `cmio` | 200 | 200 | 200* | 200 | 200* | 200 | 200 | 200* | 200 | 200 | 200 | 200 | 200 | 200 | 200* |
| `data_scientist` | 200 | 200 | 200* | 200 | 200* | 200 | 200 | 200* | 200 | 200 | 200 | 200 | 200 | 200 | 200* |
| `compliance_officer` | 200 | 200 | 200* | 200 | 200* | 200 | 200 | 200* | 200 | 200 | 200 | 200 | 200 | 200 | 200* |
| `clinical_user` | 200 | 200 | 200* | 200 | 200* | 200 | 200 | 200* | 200 | 200 | 200 | 200 | 200 | 200 | 200* |
| `analyst` | 200 | 200 | 200* | 200 | 200* | 200 | 200 | 200* | 200 | 200 | 200 | 200 | 200 | 200 | 200* |
| `viewer` | 200 | 200 | 200* | 200 | 200* | 200 | 200 | 200* | 200 | 200 | 200 | 200 | 200 | 200 | 200* |

Every row is identical. The R2 projection cannot produce silent-403 surprises because `UserRole` is not consulted on any clinic route. SEC-7's empty-page concern is therefore moot for the current codebase. Server-side reachability is a separate question and stays out of scope for R2 — if a future ticket wants role-gated clinic endpoints, server enforcement gets added at the route level alongside a projection update.

## Implementation tasks

1. **Create projection helper** — `dashboard/src/auth/clinicProductRole.ts` (new). Test: `dashboard/src/auth/__tests__/clinicProductRole.test.ts`.
2. **Property test 8×4 combinations** — assert correct projection on every (role, tier) pair.
3. **Wire projection into navigation** — `dashboard/src/config/navigation.ts:60`. Add `allowedProductRoles?: ClinicProductRole[]` to `NavSection`. Use for Practice Settings.
4. **Expose `productRole` in AuthContext** — `dashboard/src/contexts/AuthContext.tsx`.
5. **Render product role in user menu** — `dashboard/src/components/layout/AppLayout.tsx`. Replace `user?.role` print with i18n-keyed projected role when `isClinicTier(tier)`.
6. **Add i18n keys** — `clinic.role.admin`, `clinic.role.staff` in `clinic_basic.ts`, `clinic_standard.ts`, `clinic_multi_site.ts`. Spanish overlays new (HEALTH-2 bilingual requirement).
7. **Wire i18n dispatcher** — `dashboard/src/i18n/dict/index.ts`. Return Spanish overlay when `navigator.language.startsWith('es')`.
8. **Regression test — backend RBAC unchanged** — `tests/test_r2_no_backend_change.py` (new): asserts (a) `ROLE_PERMISSIONS` dict deep-equals the snapshot fixture; (b) `policy_engine/auth/rbac.py` SHA-256 matches the snapshot. CI fails on any backend RBAC change.
9. **Regression test — `cmio` JWT still hits 200** — extend `tests/test_rbac.py`: parametrise over all 8 roles × all 4 clinic routes from the matrix above.
10. **Update `getNavForUserAndTier` callers** — `dashboard/src/config/navigation.ts:218`, `AppLayout.tsx:120-123`. Pass `productRole` so a `cmio` on `clinic_basic` filters identically to a `clinical_user`.
11. **Type test for exhaustive enum** — `clinicProductRole.types.test-d.ts` (vitest type test). Catches future `UserRole` additions at compile time.
12. **Update plan-mutation log** — append "R2 landed; access matrix recorded in R2-PLAN.md" to `plans/clinical-shield-v1.md`.

## clinicProductRole.ts — verbatim

```typescript
// dashboard/src/auth/clinicProductRole.ts
import { UserRole, TierKey, isClinicTier } from '@/types';

export type ClinicProductRole = 'admin' | 'staff';
export type ProductRole = ClinicProductRole | UserRole;

const CLINIC_ADMIN_ROLES: ReadonlySet<UserRole> = new Set([
  UserRole.SYSTEM_ADMIN,
  UserRole.ADMIN,
]);

/**
 * R2 — Project the canonical 8-role backend enum into a 2-role product view
 * on clinic tiers only. Enterprise tier passes through unchanged so the
 * legacy hospital persona keeps every existing nav, label, and chip.
 *
 * Backend RBAC (policy_engine/auth/rbac.py) is the source of truth for
 * access decisions; this function is presentation-only.
 */
export function getClinicProductRole(
  role: UserRole,
  tier: TierKey,
): ProductRole {
  if (!isClinicTier(tier)) return role;
  return CLINIC_ADMIN_ROLES.has(role) ? 'admin' : 'staff';
}

/** Narrow type-guard for downstream nav filters. */
export function isClinicProductRole(value: ProductRole): value is ClinicProductRole {
  return value === 'admin' || value === 'staff';
}
```

## navigation.ts diff

```diff
@@ navigation.ts:13-19 @@ NavSection
 export interface NavSection {
   section: string;
   items: NavItem[];
   allowedRoles?: UserRole[];
+  /** R2 — gate by projected product role on clinic tiers. Ignored on enterprise. */
+  allowedProductRoles?: ClinicProductRole[];
   requiredTiers?: TierKey[];
 }
@@ navigation.ts:57-66 @@
   {
     section: 'Practice Settings',
     requiredTiers: CLINIC_ALL_TIERS,
-    allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER],
+    // R2: on clinic tiers, only the projected 'admin' product role sees
+    // Practice Settings. Server-side every authenticated user reaches the
+    // /clinic/settings/* routes (see R2-PLAN.md access matrix). Hiding the
+    // link is presentation-only.
+    allowedProductRoles: ['admin'],
     items: [
       { label: 'Practice info', path: '/clinic/settings/practice',    iconName: 'Business' },
       { label: 'Compliance',    path: '/clinic/settings/compliance',  iconName: 'HealthAndSafety' },
       { label: 'Plan & billing', path: '/clinic/settings/billing',    iconName: 'AttachMoney' },
     ],
   },
@@ navigation.ts:218 @@
-export function getNavForUserAndTier(role: UserRole, tier: TierKey): NavSection[] {
+export function getNavForUserAndTier(
+  role: UserRole,
+  tier: TierKey,
+  productRole: ProductRole = getClinicProductRole(role, tier),
+): NavSection[] {
   return NAV_SECTIONS
     .filter((sec) => tierAllowed(sec.requiredTiers, tier))
     .filter((sec) => !sec.allowedRoles || sec.allowedRoles.includes(role))
+    .filter((sec) => !sec.allowedProductRoles
+      || (isClinicProductRole(productRole) && sec.allowedProductRoles.includes(productRole)))
     .map(...);
 }
```

`navigation.ts:69-204` (all enterprise sections) stays untouched — enterprise tier uses canonical 8-role gating exclusively.

## i18n keys (en + es)

```ts
// dashboard/src/i18n/dict/clinic_basic.ts — add
'clinic.role.admin': 'Practice owner',
'clinic.role.staff': 'Staff',

// dashboard/src/i18n/dict/clinic_basic.es.ts (new)
export const clinic_basic_es: TierDict = {
  'clinic.role.admin': 'Propietario de la práctica',
  'clinic.role.staff': 'Personal',
  // overlay the rest of role.* keys for parity
};
```

`clinic_multi_site` overrides `clinic.role.admin` → `'Group administrator'` / `'Administrador del grupo'`.

## Test plan

- **Property test (`clinicProductRole.test.ts`)** — `it.each(cartesian(allEightRoles, allFourTiers))` — 32 cases. Clinic tiers → `system_admin`/`admin` → `'admin'`, others → `'staff'`. Enterprise → identity.
- **Navigation test (`navigation.test.ts`)** — `cmio` on `clinic_basic` produces nav without `Practice Settings`; same `cmio` on `enterprise` produces full hospital nav; `admin` on `clinic_basic` sees `Practice Settings`.
- **Regression (`tests/test_rbac.py`)** — must pass unchanged. CI gate: `git diff main -- policy_engine/auth/rbac.py policy_engine/models/user.py` must be empty.
- **Snapshot guard (`tests/test_r2_no_backend_change.py`)** — SHA-256 hash check on the two backend files.
- **Type test (`.test-d.ts`)** — `expectError` if a new `UserRole` member is added without updating `CLINIC_ADMIN_ROLES`.

## Verification commands

```bash
# Frontend
cd dashboard
npx tsc --noEmit
npx vitest run src/auth src/config src/contexts src/i18n
npx vitest run --coverage

# Backend regression (must be unchanged)
cd ..
pytest tests/test_rbac.py -v
pytest tests/test_r2_no_backend_change.py -v

# Diff guard
git diff main -- policy_engine/auth/rbac.py policy_engine/models/user.py
# (must print nothing)
```

## PR template body

```markdown
# R2 — Collapse clinic UX to Admin + Staff

Closes ARCH-2, SEC-7, RR-17 (plans/clinical-shield-v1.md).
Implements PRD.v2 §3.1 two-role clinic persona.

## What changed
- New: dashboard/src/auth/clinicProductRole.ts — pure (role, tier) → 'admin' | 'staff' | UserRole
- dashboard/src/config/navigation.ts — Practice Settings gated by `allowedProductRoles: ['admin']`
- dashboard/src/contexts/AuthContext.tsx — exposes `productRole`
- dashboard/src/components/layout/AppLayout.tsx — friendly role rendering on clinic tiers
- dashboard/src/i18n/dict/clinic_*.ts (+ .es.ts overlays) — `clinic.role.admin`, `clinic.role.staff`

## What did NOT change
- policy_engine/auth/rbac.py (SHA pinned in test_r2_no_backend_change.py)
- policy_engine/models/user.py UserRole enum + ROLE_PERMISSIONS dict
- Every /v1/clinic/* route (all 8 backend roles still return identical status codes)

## RR-17 access matrix
See R2-PLAN.md §"Role × clinic-route access matrix" — every row identical (no clinic route consults `UserRole`); projection therefore cannot produce silent-empty pages.

## Tier
A. Safe to merge to `main` independently.

## Test plan
- [x] property test 8×4 role/tier combinations
- [x] navigation.test.ts: cmio on clinic_basic vs enterprise
- [x] tests/test_rbac.py unchanged and green
- [x] test_r2_no_backend_change.py snapshot guard
- [x] coverage ≥ 85% on touched modules

## Reversibility
Revert is one commit; backend enum untouched.

## Reviewers
- `typescript-reviewer` — projection + nav diff
- `security-reviewer` — RR-17 closeout (access matrix derivation)
- `code-reviewer` — final
```
