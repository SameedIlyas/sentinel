/**
 * Clinic Standard — Spanish overlay.
 *
 * Inherits clinic_basic_es. Two intentional purposes:
 *  - (A1) Training-status banner copy is identical to clinic_basic_es —
 *    Standard does not diverge there. Pending healthcare-reviewer sign-off.
 *  - (R2 + HEALTH-2) Standard-only role override: compliance_officer
 *    becomes "Responsable de cumplimiento" (matches the English
 *    clinic_standard.ts override).
 */

import type { TierDict } from './types';
import { clinic_basic_es } from './clinic_basic.es';

export const clinic_standard_es: TierDict = {
  ...clinic_basic_es,
  // Standard-only Spanish overrides land here.
  'role.compliance_officer': 'Responsable de cumplimiento',
};
