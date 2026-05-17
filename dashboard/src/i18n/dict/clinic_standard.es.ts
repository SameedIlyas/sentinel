/**
 * R2 + HEALTH-2 — Spanish (es) overlay for the clinic_standard dictionary.
 * Inherits from clinic_basic_es; standard does not change the projected role
 * labels.
 */

import type { TierDict } from './types';
import { clinic_basic_es } from './clinic_basic.es';

export const clinic_standard_es: TierDict = {
  ...clinic_basic_es,
  // Standard-only Spanish overrides land here.
  'role.compliance_officer': 'Responsable de cumplimiento',
};
