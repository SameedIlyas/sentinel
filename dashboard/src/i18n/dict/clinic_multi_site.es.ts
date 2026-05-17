/**
 * Clinic Multi-Site — Spanish overlay.
 *
 * Inherits clinic_standard_es. Two intentional purposes:
 *  - (A1) Training-status banner copy is identical to clinic_standard_es
 *    via inheritance — Multi-site does not diverge there. Strings pending
 *    healthcare-reviewer sign-off.
 *  - (R2 + HEALTH-2) Group/site vocabulary plus projected admin label
 *    becoming "Administrador del grupo" (matches clinic_multi_site.ts).
 */

import type { TierDict } from './types';
import { clinic_standard_es } from './clinic_standard.es';

export const clinic_multi_site_es: TierDict = {
  ...clinic_standard_es,
  'noun.organization': 'Grupo de prácticas',
  'noun.organizations': 'Grupos de prácticas',
  'role.admin': 'Administrador del grupo',
  'role.cmio': 'Director médico',

  // R2 — projected admin becomes "group administrator" on multi-site.
  'clinic.role.admin': 'Administrador del grupo',
};
