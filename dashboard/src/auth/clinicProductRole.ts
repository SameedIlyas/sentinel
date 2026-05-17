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

export type ClinicProductRole = 'admin' | 'staff';

/** A role as rendered in the UI: either a projected clinic role or, on the
 *  enterprise tier, the backend `UserRole` itself. */
export type ProductRole = ClinicProductRole | UserRole;

const CLINIC_ADMIN_ROLES: ReadonlySet<UserRole> = new Set<UserRole>([
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
export function isClinicProductRole(
  value: ProductRole,
): value is ClinicProductRole {
  return value === 'admin' || value === 'staff';
}
