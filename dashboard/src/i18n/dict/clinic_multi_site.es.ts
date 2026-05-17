/**
 * R2 + HEALTH-2 — Spanish (es) overlay for the clinic_multi_site dictionary.
 * Group/site vocabulary on top of clinic_standard_es.
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
