/**
 * Clinic Multi-Site — Spanish overlay (PRD.v2.md §6.8.2.b).
 * Currently identical to ``clinic_standard_es`` — Multi-site tier does
 * not diverge in training-status copy. Strings pending healthcare-
 * reviewer sign-off.
 */

import type { TierDict } from './types';
import { clinic_standard_es } from './clinic_standard.es';

export const clinic_multi_site_es: TierDict = {
  ...clinic_standard_es,
};
