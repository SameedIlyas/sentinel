/**
 * R2 — Property test for the (role, tier) → product-role projection.
 *
 * The projection is a pure function with a small finite domain (8 backend
 * roles × 4 tier keys = 32 cases). Enumerate every combination so a future
 * change to either axis is forced to update this test.
 *
 * Rules:
 *  - On clinic tiers, SYSTEM_ADMIN and ADMIN project to 'admin'; everything
 *    else projects to 'staff'.
 *  - On enterprise tier, projection is identity (backend role).
 */

import { describe, expect, it } from 'vitest';
import { UserRole, type TierKey } from '@/types';
import {
  getClinicProductRole,
  isClinicProductRole,
  type ProductRole,
} from '../clinicProductRole';

const ALL_ROLES: UserRole[] = [
  UserRole.SYSTEM_ADMIN,
  UserRole.ADMIN,
  UserRole.CMIO,
  UserRole.DATA_SCIENTIST,
  UserRole.COMPLIANCE_OFFICER,
  UserRole.CLINICAL_USER,
  UserRole.ANALYST,
  UserRole.VIEWER,
];

const ALL_TIERS: TierKey[] = [
  'enterprise',
  'clinic_basic',
  'clinic_standard',
  'clinic_multi_site',
];

const CLINIC_TIERS: TierKey[] = [
  'clinic_basic',
  'clinic_standard',
  'clinic_multi_site',
];

const ADMIN_BACKEND_ROLES = new Set<UserRole>([
  UserRole.SYSTEM_ADMIN,
  UserRole.ADMIN,
]);

function cartesian<A, B>(xs: A[], ys: B[]): Array<[A, B]> {
  const out: Array<[A, B]> = [];
  for (const x of xs) for (const y of ys) out.push([x, y]);
  return out;
}

describe('getClinicProductRole — 8 roles × 4 tiers', () => {
  const cases = cartesian(ALL_ROLES, ALL_TIERS);

  it.each(cases)(
    'projects role=%s tier=%s correctly',
    (role, tier) => {
      const result = getClinicProductRole(role, tier);
      if (tier === 'enterprise') {
        // Identity on enterprise tier — backend role passes through.
        expect(result).toBe(role);
        return;
      }
      // Clinic tier: SYSTEM_ADMIN / ADMIN → 'practice_owner';
      // all six others → 'practice_staff' (review HIGH #5 rename).
      if (ADMIN_BACKEND_ROLES.has(role)) {
        expect(result).toBe('practice_owner');
      } else {
        expect(result).toBe('practice_staff');
      }
    },
  );

  it('returns identity (backend role) on enterprise for every role', () => {
    for (const role of ALL_ROLES) {
      expect(getClinicProductRole(role, 'enterprise')).toBe(role);
    }
  });

  it.each(CLINIC_TIERS)(
    "on clinic tier %s, projects 'practice_owner' iff backend role is admin/system_admin",
    (tier) => {
      for (const role of ALL_ROLES) {
        const projected = getClinicProductRole(role, tier);
        const expected = ADMIN_BACKEND_ROLES.has(role)
          ? 'practice_owner'
          : 'practice_staff';
        expect(projected).toBe(expected);
      }
    },
  );

  it('count check: 32 cases enumerated', () => {
    expect(cases.length).toBe(32);
  });
});

describe('isClinicProductRole type guard', () => {
  it("recognises 'practice_owner' and 'practice_staff' as ClinicProductRole", () => {
    expect(isClinicProductRole('practice_owner')).toBe(true);
    expect(isClinicProductRole('practice_staff')).toBe(true);
  });

  it('rejects every backend UserRole (no string overlap with renamed literals)', () => {
    // Review HIGH #5 — the projected literals were renamed from
    // 'admin' | 'staff' to 'practice_owner' | 'practice_staff' so that
    // a UserRole.ADMIN (= 'admin') no longer satisfies the guard by
    // string equality. Every backend role (including ADMIN) is now
    // rejected.
    for (const role of ALL_ROLES) {
      const value: ProductRole = role;
      expect(isClinicProductRole(value)).toBe(false);
    }
  });
});
