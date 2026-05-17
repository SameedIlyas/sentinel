/**
 * R2 — Navigation tests for the product-role projection.
 *
 * Validates that `getNavForUserAndTier` collapses the 8-role backend view
 * to the 2-role clinic product view on clinic tiers, while leaving the
 * enterprise (hospital) nav untouched.
 */

import { describe, expect, it } from 'vitest';
import { UserRole, type TierKey } from '@/types';
import { getNavForUserAndTier } from '../navigation';

function sectionNames(role: UserRole, tier: TierKey): string[] {
  return getNavForUserAndTier(role, tier).map((s) => s.section);
}

describe('getNavForUserAndTier — clinic-tier projection (R2)', () => {
  it('hides Practice Settings from a cmio user on clinic_basic (projects to staff)', () => {
    const sections = sectionNames(UserRole.CMIO, 'clinic_basic');
    expect(sections).toContain('Practice');
    expect(sections).not.toContain('Practice Settings');
  });

  it.each([
    UserRole.CMIO,
    UserRole.DATA_SCIENTIST,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.CLINICAL_USER,
    UserRole.ANALYST,
    UserRole.VIEWER,
  ])(
    'hides Practice Settings on clinic_basic from non-admin backend role %s',
    (role) => {
      expect(sectionNames(role, 'clinic_basic')).not.toContain(
        'Practice Settings',
      );
    },
  );

  it.each([UserRole.SYSTEM_ADMIN, UserRole.ADMIN])(
    'shows Practice Settings on clinic_basic for admin backend role %s',
    (role) => {
      const sections = sectionNames(role, 'clinic_basic');
      expect(sections).toContain('Practice Settings');
    },
  );

  it.each<TierKey>(['clinic_basic', 'clinic_standard', 'clinic_multi_site'])(
    'admin sees Practice Settings on tier %s',
    (tier) => {
      expect(sectionNames(UserRole.ADMIN, tier)).toContain('Practice Settings');
    },
  );

  it.each<TierKey>(['clinic_basic', 'clinic_standard', 'clinic_multi_site'])(
    'staff (cmio) does not see Practice Settings on tier %s',
    (tier) => {
      expect(sectionNames(UserRole.CMIO, tier)).not.toContain(
        'Practice Settings',
      );
    },
  );

  it('shows no enterprise sections on a clinic tier', () => {
    const sections = sectionNames(UserRole.ADMIN, 'clinic_basic');
    for (const enterprise of [
      'Core',
      'Clinical Governance',
      'Admin Governance',
      'Financial',
      'Regulatory',
      'Risk',
      'Settings',
    ]) {
      expect(sections).not.toContain(enterprise);
    }
  });
});

describe('getNavForUserAndTier — enterprise tier is unchanged', () => {
  it('cmio on enterprise still sees the full hospital nav (no clinic projection)', () => {
    const sections = sectionNames(UserRole.CMIO, 'enterprise');
    // cmio is allowed in Clinical Governance + Risk per existing nav config.
    expect(sections).toContain('Clinical Governance');
    expect(sections).toContain('Risk');
    // No clinic sections appear.
    expect(sections).not.toContain('Practice');
    expect(sections).not.toContain('Practice Settings');
  });

  it('admin on enterprise sees Settings (which is enterprise-only)', () => {
    expect(sectionNames(UserRole.ADMIN, 'enterprise')).toContain('Settings');
  });

  it('viewer on enterprise still sees Core but not admin-only sections', () => {
    const sections = sectionNames(UserRole.VIEWER, 'enterprise');
    expect(sections).toContain('Core');
    expect(sections).not.toContain('Settings');
  });
});

describe('getNavForUserAndTier — explicit productRole override', () => {
  it('forcing productRole=staff on clinic_basic hides Practice Settings even for an admin backend role', () => {
    const sections = getNavForUserAndTier(UserRole.ADMIN, 'clinic_basic', 'staff')
      .map((s) => s.section);
    expect(sections).not.toContain('Practice Settings');
  });

  it("forcing productRole='admin' on clinic_basic shows Practice Settings for a staff backend role", () => {
    const sections = getNavForUserAndTier(UserRole.CMIO, 'clinic_basic', 'admin')
      .map((s) => s.section);
    expect(sections).toContain('Practice Settings');
  });
});
