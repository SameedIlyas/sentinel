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
function assertExhaustive(role: UserRole): ClinicProductRole {
  switch (role) {
    case UserRole.SYSTEM_ADMIN:
    case UserRole.ADMIN:
      return 'practice_owner';
    case UserRole.CMIO:
    case UserRole.DATA_SCIENTIST:
    case UserRole.COMPLIANCE_OFFICER:
    case UserRole.CLINICAL_USER:
    case UserRole.ANALYST:
    case UserRole.VIEWER:
      return 'practice_staff';
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

// `ClinicProductRole` is exactly the 2-element string union (review
// HIGH #5 — renamed from 'admin' | 'staff' to remove UserRole.ADMIN
// string-equality collision).
const _owner: ClinicProductRole = 'practice_owner';
const _staff: ClinicProductRole = 'practice_staff';

// Review HIGH #5 — a raw UserRole.ADMIN must NOT be assignable to
// ClinicProductRole. The @ts-expect-error directive proves the type
// guard now catches what previously slipped through.
// @ts-expect-error UserRole.ADMIN is no longer assignable to ClinicProductRole
const _adminLeak: ClinicProductRole = UserRole.ADMIN;
void _adminLeak;

// `ProductRole` is the union of ClinicProductRole and UserRole. A plain
// UserRole literal must be assignable.
const _user: ProductRole = UserRole.VIEWER;
const _staffP: ProductRole = 'practice_staff';

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
  _owner,
  _staff,
  _user,
  _staffP,
  _projection,
  _narrowing('practice_owner'),
] as const;
