import { describe, it, expect } from 'vitest';

import { clinic_basic } from '../dict/clinic_basic';
import { clinic_standard } from '../dict/clinic_standard';
import { clinic_multi_site } from '../dict/clinic_multi_site';
import { enterprise } from '../dict/enterprise';
import { clinic_basic_es } from '../dict/clinic_basic.es';
import { clinic_standard_es } from '../dict/clinic_standard.es';
import { clinic_multi_site_es } from '../dict/clinic_multi_site.es';

const TRAINING_KEYS = [
  'clinic.tools.training_status.warning_no_baa',
  'clinic.tools.training_status.warning_baa_present',
  'clinic.tools.training_status.opt_out_required',
  'clinic.tools.training_status.opt_out_verified',
  'clinic.tools.training_status.unknown',
] as const;

describe('clinic.tools.training_status — locked i18n keys (PRD.v2.md §6.8.2.b)', () => {
  it.each(TRAINING_KEYS)('English key %s present in enterprise fallback', (key) => {
    expect(enterprise[key]).toBeTruthy();
  });

  it.each(TRAINING_KEYS)('English key %s present in clinic_basic', (key) => {
    expect(clinic_basic[key]).toBeTruthy();
  });

  it.each(TRAINING_KEYS)('English key %s present in clinic_standard', (key) => {
    expect(clinic_standard[key]).toBeTruthy();
  });

  it.each(TRAINING_KEYS)('English key %s present in clinic_multi_site', (key) => {
    expect(clinic_multi_site[key]).toBeTruthy();
  });

  it.each(TRAINING_KEYS)('Spanish key %s present in clinic_basic_es', (key) => {
    expect(clinic_basic_es[key]).toBeTruthy();
  });

  it.each(TRAINING_KEYS)('Spanish key %s present in clinic_standard_es', (key) => {
    expect(clinic_standard_es[key]).toBeTruthy();
  });

  it.each(TRAINING_KEYS)('Spanish key %s present in clinic_multi_site_es', (key) => {
    expect(clinic_multi_site_es[key]).toBeTruthy();
  });

  it('opt_out_verified template has {date} and {user} placeholders', () => {
    expect(clinic_basic['clinic.tools.training_status.opt_out_verified']).toContain(
      '{date}',
    );
    expect(clinic_basic['clinic.tools.training_status.opt_out_verified']).toContain(
      '{user}',
    );
    expect(
      clinic_basic_es['clinic.tools.training_status.opt_out_verified'],
    ).toContain('{date}');
    expect(
      clinic_basic_es['clinic.tools.training_status.opt_out_verified'],
    ).toContain('{user}');
  });
});
