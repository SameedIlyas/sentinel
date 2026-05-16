/**
 * Regression test for HIGH-026 — TierKey must be runtime-validated.
 *
 * AuthContext.tsx:184 and AppLayout.tsx:121-122 historically cast user?.tier
 * to TierKey with `as TierKey`, suppressing every TypeScript check. A backend
 * response carrying an unrecognised tier string (e.g. a newly-rolled SKU
 * "clinic_pro") would pass the cast unchanged, but every downstream
 * `tierAllowed()` filter returns false, leaving the user with a blank
 * sidebar and no error to indicate what went wrong.
 *
 * resolveTier(raw) validates the input against the four known TierKey
 * literals and falls back to 'enterprise' on anything unknown, including
 * null/undefined and non-string values.
 */
import { describe, expect, it } from 'vitest';
import { resolveTier, isClinicTier } from './index';

describe('resolveTier (HIGH-026)', () => {
  it.each([
    ['enterprise'],
    ['clinic_basic'],
    ['clinic_standard'],
    ['clinic_multi_site'],
  ])('passes through the canonical tier %s', (input) => {
    expect(resolveTier(input)).toBe(input);
  });

  it.each([null, undefined, ''])('falls back to enterprise for %p', (input) => {
    expect(resolveTier(input)).toBe('enterprise');
  });

  it.each(['clinic_pro', 'CLINIC_BASIC', 'free', 'admin', 'enterprise '])(
    'falls back to enterprise for unrecognised string %p',
    (input) => {
      expect(resolveTier(input)).toBe('enterprise');
    },
  );

  it.each([42, true, {}, [], () => {}])(
    'falls back to enterprise for non-string %p',
    (input) => {
      expect(resolveTier(input)).toBe('enterprise');
    },
  );

  it('resolveTier output is always recognised by isClinicTier or the enterprise check', () => {
    const inputs = ['clinic_basic', 'unknown', null, 99];
    for (const input of inputs) {
      const tier = resolveTier(input);
      expect(tier === 'enterprise' || isClinicTier(tier)).toBe(true);
    }
  });
});
