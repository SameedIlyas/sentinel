/**
 * Clinic Basic dictionary — overrides over the canonical enterprise
 * dictionary.  Keep entries strictly limited to terms that *change*; rely
 * on fall-through for everything else so we don't drift.
 */

import type { TierDict } from './types';

export const clinic_basic: TierDict = {
  'noun.organization': 'Practice',
  'noun.organizations': 'Practices',
  'noun.member': 'Staff member',
  'noun.members': 'Staff',
  'noun.alert': 'Notification',
  'noun.alerts': 'Notifications',
  'noun.policy': 'Practice rule',
  'noun.policies': 'Practice rules',
  'noun.audit_log': 'Activity log',
  'noun.audit_logs': 'Activity log',
  'noun.agent': 'AI tool',
  'noun.agents': 'AI tools',
  'noun.model_card': 'AI tool',
  'noun.model_cards': 'AI tools',
  'noun.bias_audit': 'Fairness check',
  'noun.bias_audits': 'Fairness checks',
  'noun.drift': 'Tool behavior monitor',
  'noun.hitl_queue': 'Things to review',
  'noun.shadow_ai': 'Unsanctioned tools',
  'noun.tool_registry': 'AI tool registry',

  'role.system_admin': 'Sentinel admin',
  'role.admin': 'Practice owner',
  'role.cmio': 'Lead clinician',
  'role.data_scientist': 'AI lead',
  'role.compliance_officer': 'Office manager',
  'role.clinical_user': 'Clinician',
  'role.analyst': 'Reviewer',
  'role.viewer': 'Observer',

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
