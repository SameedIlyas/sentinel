/**
 * R2 + HEALTH-2 — Spanish (es) overlay for the clinic_basic dictionary.
 *
 * Partial map: only the keys we have a Spanish translation for. Lookups
 * fall through to `clinic_basic` (English) for anything missing so the
 * surface degrades gracefully — never to a raw enum key.
 */

import type { TierDict } from './types';

export const clinic_basic_es: TierDict = {
  // ── Projected product role (R2) ────────────────────────────────────
  'clinic.role.admin': 'Propietario de la práctica',
  'clinic.role.staff': 'Personal',

  // ── Canonical role labels — Spanish parity with clinic_basic ───────
  'role.system_admin': 'Administrador Sentinel',
  'role.admin': 'Propietario de la práctica',
  'role.cmio': 'Clínico principal',
  'role.data_scientist': 'Responsable de IA',
  'role.compliance_officer': 'Gerente de oficina',
  'role.clinical_user': 'Clínico',
  'role.analyst': 'Revisor',
  'role.viewer': 'Observador',
};
