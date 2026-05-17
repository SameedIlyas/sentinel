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

  // PRD.v2.md §6.8.2.b — locked training-status banner copy. DO NOT
  // edit verbatim strings without healthcare-reviewer sign-off.
  // Block intentionally kept at the same location across clinic_basic /
  // clinic_standard / clinic_multi_site for trivial three-way merge.
  'clinic.tools.training_status.warning_no_baa':
    'This tool may train its models on what you type here. Treat anything entered as disclosed outside your practice. Do not enter patient information unless your written BAA with the vendor explicitly permits training use — most BAAs do not.',
  'clinic.tools.training_status.warning_baa_present':
    "This tool's vendor trains on prompts, but your BAA permits this use. Patient information is still handled under the BAA's terms — confirm with your compliance lead before entering new categories of PHI.",
  'clinic.tools.training_status.opt_out_required':
    "This tool trains on prompts unless you turn it off in the vendor's settings. Confirm the opt-out is set, then mark this tool as Verified in Sentinel.",
  'clinic.tools.training_status.opt_out_verified':
    'Opt-out verified on {date} by {user}.',
  'clinic.tools.training_status.unknown':
    'Status not yet confirmed — assign to a practice admin to investigate.',
};
