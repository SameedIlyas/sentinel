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
};
