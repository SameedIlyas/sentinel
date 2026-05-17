/**
 * R2 — `clinic.role.admin` / `clinic.role.staff` must exist in every
 * clinic-tier dictionary so the AppLayout user-menu projection (see
 * `AppLayout.tsx` → `roleLabel`) never falls through to the raw enum key.
 *
 * Includes Spanish (`.es.ts`) parity check per HEALTH-2 bilingual requirement.
 */

import { describe, expect, it } from 'vitest';

import { clinic_basic } from '../dict/clinic_basic';
import { clinic_standard } from '../dict/clinic_standard';
import { clinic_multi_site } from '../dict/clinic_multi_site';
import { clinic_basic_es } from '../dict/clinic_basic.es';
import { clinic_standard_es } from '../dict/clinic_standard.es';
import { clinic_multi_site_es } from '../dict/clinic_multi_site.es';
import { resolveDict, resolveDictLocale } from '../dict';

const PROJECTED_ROLE_KEYS = ['clinic.role.admin', 'clinic.role.staff'] as const;

describe('clinic.role.* keys present in every clinic dictionary (R2)', () => {
  it.each(PROJECTED_ROLE_KEYS)(
    'clinic_basic has %s',
    (key) => {
      expect(clinic_basic[key]).toBeTruthy();
    },
  );

  it.each(PROJECTED_ROLE_KEYS)(
    'clinic_standard has %s',
    (key) => {
      expect(clinic_standard[key]).toBeTruthy();
    },
  );

  it.each(PROJECTED_ROLE_KEYS)(
    'clinic_multi_site has %s',
    (key) => {
      expect(clinic_multi_site[key]).toBeTruthy();
    },
  );

  it('multi_site renders clinic.role.admin as the group label, not the practice-owner label', () => {
    // PRD.v2 §3.1 — multi-site admins are group administrators.
    expect(clinic_multi_site['clinic.role.admin']).not.toBe(
      clinic_basic['clinic.role.admin'],
    );
    expect(clinic_multi_site['clinic.role.admin']).toMatch(/group/i);
  });
});

describe('Spanish overlays parity (R2 + HEALTH-2)', () => {
  it.each(PROJECTED_ROLE_KEYS)(
    'clinic_basic_es has %s',
    (key) => {
      expect(clinic_basic_es[key]).toBeTruthy();
    },
  );

  it.each(PROJECTED_ROLE_KEYS)(
    'clinic_standard_es has %s',
    (key) => {
      expect(clinic_standard_es[key]).toBeTruthy();
    },
  );

  it.each(PROJECTED_ROLE_KEYS)(
    'clinic_multi_site_es has %s',
    (key) => {
      expect(clinic_multi_site_es[key]).toBeTruthy();
    },
  );

  it('Spanish multi_site clinic.role.admin overrides the basic/staff overlay', () => {
    expect(clinic_multi_site_es['clinic.role.admin']).not.toBe(
      clinic_basic_es['clinic.role.admin'],
    );
  });
});

describe('resolveDictLocale dispatches to the right overlay', () => {
  it("returns the Spanish overlay for locale='es'", () => {
    const dict = resolveDictLocale('clinic_basic', 'es');
    expect(dict['clinic.role.admin']).toBe(
      clinic_basic_es['clinic.role.admin'],
    );
  });

  it("returns the Spanish overlay for locale='es-MX'", () => {
    const dict = resolveDictLocale('clinic_basic', 'es-MX');
    expect(dict['clinic.role.admin']).toBe(
      clinic_basic_es['clinic.role.admin'],
    );
  });

  it("returns the English dict for locale='en'", () => {
    const dict = resolveDictLocale('clinic_basic', 'en');
    expect(dict['clinic.role.admin']).toBe(
      clinic_basic['clinic.role.admin'],
    );
  });

  it("falls back to English for locale=undefined", () => {
    const dict = resolveDictLocale('clinic_basic', undefined);
    expect(dict['clinic.role.admin']).toBe(
      clinic_basic['clinic.role.admin'],
    );
  });

  it('on enterprise tier, ignores locale (no Spanish enterprise overlay yet)', () => {
    const dict = resolveDictLocale('enterprise', 'es');
    // enterprise has no clinic.role.* keys; resolveDictLocale should still
    // return the enterprise dict (parity with resolveDict).
    expect(dict).toBe(resolveDict('enterprise'));
  });
});
