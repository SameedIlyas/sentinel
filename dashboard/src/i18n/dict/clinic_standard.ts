/**
 * Clinic Standard dictionary — extends ``clinic_basic``.  Keep this file
 * limited to terms that genuinely differ between Basic and Standard.
 * Today there is no diff (Standard adds *features*, not vocabulary), so
 * this is a thin re-export.  Future tier-specific copy lives here.
 */

import type { TierDict } from './types';
import { clinic_basic } from './clinic_basic';

export const clinic_standard: TierDict = {
  ...clinic_basic,
  // Standard-only features get clinic-friendly labels here.
  'role.compliance_officer': 'Compliance lead',
};
