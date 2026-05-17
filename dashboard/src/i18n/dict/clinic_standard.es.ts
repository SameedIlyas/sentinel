/**
 * Clinic Standard — Spanish overlay (PRD.v2.md §6.8.2.b).
 * Currently identical to ``clinic_basic_es`` — Standard tier does not
 * diverge in training-status copy. Strings pending healthcare-reviewer
 * sign-off.
 */

import type { TierDict } from './types';
import { clinic_basic_es } from './clinic_basic.es';

export const clinic_standard_es: TierDict = {
  ...clinic_basic_es,
};
