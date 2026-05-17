/**
 * R2 — Compile-time exhaustiveness check for clinicProductRole.
 *
 * This file is type-checked by `tsc --noEmit` (vitest does not need to
 * execute it). If a new `UserRole` member is added without also updating
 * the projection helper, the `never`-typed switch below stops compiling
 * and CI fails. That is the safety net that keeps the eight backend
 * roles in sync with the projection.
 *
 * The file deliberately ends in `.test-d.ts` so it is picked up by the
 * existing tsconfig include but is not executed as a runtime test (no
 * vitest typecheck config required).
 */

import { UserRole } from '@/types';
import {
  getClinicProductRole,
  isClinicProductRole,
  type ClinicProductRole,
  type ProductRole,
} from '../clinicProductRole';

// Exhaustive switch on UserRole — every member must be handled.
function assertExhaustive(role: UserRole): 'admin' | 'staff' {
  switch (role) {
    case UserRole.SYSTEM_ADMIN:
    case UserRole.ADMIN:
      return 'admin';
    case UserRole.CMIO:
    case UserRole.DATA_SCIENTIST:
    case UserRole.COMPLIANCE_OFFICER:
    case UserRole.CLINICAL_USER:
    case UserRole.ANALYST:
    case UserRole.VIEWER:
      return 'staff';
    default: {
      // If a new UserRole member is added without extending the switch
      // above, `role` will not narrow to `never` here and this line will
      // fail to compile.
      const _exhaustive: never = role;
      return _exhaustive;
    }
  }
}

// ── Type-level assertions ──────────────────────────────────────────────

// `ClinicProductRole` is exactly the 2-element string union.
const _admin: ClinicProductRole = 'admin';
const _staff: ClinicProductRole = 'staff';

// `ProductRole` is the union of ClinicProductRole and UserRole. A plain
// UserRole literal must be assignable.
const _user: ProductRole = UserRole.VIEWER;
const _staffP: ProductRole = 'staff';

// `getClinicProductRole` must accept (UserRole, TierKey) and return ProductRole.
const _projection: ProductRole = getClinicProductRole(UserRole.CMIO, 'clinic_basic');

// `isClinicProductRole` narrows ProductRole to ClinicProductRole.
function _narrowing(value: ProductRole): ClinicProductRole | null {
  if (isClinicProductRole(value)) {
    const narrowed: ClinicProductRole = value; // narrowing must succeed
    return narrowed;
  }
  return null;
}

// Use the assertExhaustive helper to silence unused-var lints while
// keeping the exhaustiveness behaviour observable.
export const _r2TypeTestEntries = [
  assertExhaustive(UserRole.SYSTEM_ADMIN),
  assertExhaustive(UserRole.VIEWER),
  _admin,
  _staff,
  _user,
  _staffP,
  _projection,
  _narrowing('admin'),
] as const;
