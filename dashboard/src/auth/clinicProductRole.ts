// dashboard/src/auth/clinicProductRole.ts
//
// R2 — Frontend-only projection of the canonical 8-role backend enum onto
// a 2-role product view (`admin` / `staff`) for clinic tiers. Enterprise
// tier renders the 8-role view unchanged (preserves the legacy hospital
// persona).
//
// This file is presentation-only. Backend RBAC (`policy_engine/auth/rbac.py`)
// and `ROLE_PERMISSIONS` (`policy_engine/models/user.py`) remain the source of
// truth for access decisions. See plans/clinical-shield-v1/R2-PLAN.md.

import { UserRole, type TierKey, isClinicTier } from '@/types';

/**
 * Projected clinic product-role literals.
 *
 * Review HIGH #5 — these were originally ``'admin' | 'staff'`` which
 * collided at runtime with ``UserRole.ADMIN`` (= ``'admin'``). An
 * enterprise-tier user with backend role ``ADMIN`` could pass
 * ``isClinicProductRole`` by string equality, a latent hole masked only
 * by the nav filter's ``requiredTiers`` check firing first. Renaming
 * the literals to ``'practice_owner' | 'practice_staff'`` removes the
 * collision at the type level *and* at runtime.
 *
 * i18n keys (``clinic.role.admin`` / ``clinic.role.staff``) and ROLE_COLORS
 * entries are unchanged — call sites translate via
 * ``CLINIC_PRODUCT_ROLE_I18N_SUFFIX`` below.
 */
export type ClinicProductRole = 'practice_owner' | 'practice_staff';

/** A role as rendered in the UI: either a projected clinic role or, on the
 *  enterprise tier, the backend `UserRole` itself. */
export type ProductRole = ClinicProductRole | UserRole;

const CLINIC_ADMIN_ROLES: ReadonlySet<UserRole> = new Set<UserRole>([
  UserRole.SYSTEM_ADMIN,
  UserRole.ADMIN,
]);

/**
 * Maps the projected clinic product-role literals to the short i18n key
 * suffixes preserved from the original 'admin' / 'staff' projection. The
 * full i18n keys are ``clinic.role.admin`` / ``clinic.role.staff`` and
 * the matching ROLE_COLORS entries also live under those keys.
 *
 * Exported so AppLayout (and any future renderer) can translate the
 * type-safe literal back to the locked translation keys without
 * hardcoding the mapping in two places.
 */
export const CLINIC_PRODUCT_ROLE_I18N_SUFFIX: Record<
  ClinicProductRole,
  'admin' | 'staff'
> = {
  practice_owner: 'admin',
  practice_staff: 'staff',
};

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
  return CLINIC_ADMIN_ROLES.has(role) ? 'practice_owner' : 'practice_staff';
}

/** Narrow type-guard for downstream nav filters. */
export function isClinicProductRole(
  value: ProductRole,
): value is ClinicProductRole {
  return value === 'practice_owner' || value === 'practice_staff';
}
