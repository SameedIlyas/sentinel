/**
 * Canonical (enterprise) display strings — the source of truth.
 *
 * Every key used by `useT()` *must* be present here.  Tier-specific
 * dictionaries are a partial override; missing keys fall through to this
 * file so that adding a new term in one place keeps the platform
 * functional even before clinic translations are written.
 */

import type { TierDict } from './types';

export const enterprise: TierDict = {
  // ── App-wide ───────────────────────────────────────────────────────
  'app.product_name': 'Sentinel AI',
  'app.tagline': 'Healthcare AI governance',

  // ── Persona-level vocabulary ───────────────────────────────────────
  'noun.organization': 'Organization',
  'noun.organizations': 'Organizations',
  'noun.member': 'Member',
  'noun.members': 'Members',
  'noun.alert': 'Alert',
  'noun.alerts': 'Alerts',
  'noun.policy': 'Policy',
  'noun.policies': 'Policies',
  'noun.audit_log': 'Audit Log',
  'noun.audit_logs': 'Audit Logs',
  'noun.agent': 'AI Agent',
  'noun.agents': 'AI Agents',
  'noun.model_card': 'Model Card',
  'noun.model_cards': 'Model Cards',
  'noun.bias_audit': 'Bias Audit',
  'noun.bias_audits': 'Bias Audits',
  'noun.drift': 'Drift Monitor',
  'noun.hitl_queue': 'HITL Queue',
  'noun.shadow_ai': 'Shadow AI',
  'noun.tool_registry': 'Model Cards',

  // ── Role labels (display only) ─────────────────────────────────────
  'role.system_admin': 'System Admin',
  'role.admin': 'Org Admin',
  'role.cmio': 'CMIO',
  'role.data_scientist': 'Data Scientist',
  'role.compliance_officer': 'Compliance Officer',
  'role.clinical_user': 'Clinical User',
  'role.analyst': 'Analyst',
  'role.viewer': 'Viewer',

  // ── Navigation sections ────────────────────────────────────────────
  'nav.section.core': 'Core',
  'nav.section.clinical': 'Clinical Governance',
  'nav.section.admin_governance': 'Admin Governance',
  'nav.section.financial': 'Financial',
  'nav.section.regulatory': 'Regulatory',
  'nav.section.risk': 'Risk',
  'nav.section.settings': 'Settings',
  'nav.section.clinic': 'Practice',
  'nav.section.clinic_settings': 'Practice Settings',

  // ── Clinic-specific keys (enterprise fallback values used only when
  //    a clinic page is somehow viewed by an enterprise user) ─────────
  'clinic.dashboard.title': 'Dashboard',
  'clinic.dashboard.welcome': 'Welcome back',
  'clinic.dashboard.tools_tile': 'Registered models',
  'clinic.dashboard.alerts_tile': 'Open alerts',
  'clinic.dashboard.blocked_tile': 'Blocked actions today',
  'clinic.dashboard.report_tile': 'Latest compliance report',
  'clinic.dashboard.tools_subtitle': 'AI tools under management',
  'clinic.dashboard.alerts_subtitle': 'Need acknowledgement',
  'clinic.dashboard.blocked_subtitle': 'Risky actions stopped',
  'clinic.dashboard.report_subtitle': 'Regulator-ready PDF',

  'clinic.tools.list_title': 'AI tools',
  'clinic.tools.list_subtitle':
    'Every AI tool your practice uses — sanctioned or otherwise.',
  'clinic.tools.add': 'Register a tool',
  'clinic.tools.empty':
    'No tools registered yet. Add your first AI tool to get started.',
  'clinic.tools.field.name': 'Tool name',
  'clinic.tools.field.vendor': 'Vendor',
  'clinic.tools.field.category': 'What does it do?',
  'clinic.tools.field.purpose': 'Purpose',
  'clinic.tools.field.handles_phi': 'Does this tool see patient information?',
  'clinic.tools.field.risk_level': 'Risk level',
  'clinic.tools.field.notes': 'Notes',
  'clinic.tools.field.model_training_status': 'Does the vendor train on your data?',
  'clinic.tools.field.practice_opt_out_state': 'Opt-out status in your account',
  'clinic.tools.field.model_training_status_evidence':
    'Where did you confirm this? (link or note)',

  // Locked training-status banner copy — PRD.v2.md §6.8.2.b. DO NOT
  // edit verbatim strings without healthcare-reviewer sign-off.
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

  'clinic.policies.title': 'Practice rules',
  'clinic.policies.subtitle':
    'Pick from a library of pre-written rules — apply with one click.',
  'clinic.policies.applied': 'Applied',
  'clinic.policies.apply': 'Apply this rule',
  'clinic.policies.why_it_matters': 'Why it matters',

  'clinic.alerts.title': 'What needs your attention',
  'clinic.alerts.empty': 'Nothing on fire — well done.',
  'clinic.alerts.next_step': 'What to do',

  'clinic.settings.practice': 'Practice info',
  'clinic.settings.compliance': 'Compliance',
  'clinic.settings.billing': 'Plan & billing',
  'clinic.settings.baa.title': 'Business Associate Agreement',
  'clinic.settings.baa.click_through_intro':
    'Your plan uses a click-through BAA. Confirm the details below to enable HIPAA-covered features.',
  'clinic.settings.baa.executed_intro':
    'Your plan includes an executed BAA. Your account manager will send a copy for signature.',
  'clinic.settings.baa.signed_on': 'Signed on',
  'clinic.settings.baa.accept_button': 'Accept BAA',

  'clinic.onboarding.title': 'Get your practice set up',
  'clinic.onboarding.step.baa': 'Sign your BAA',
  'clinic.onboarding.step.tool': 'Register your first AI tool',
  'clinic.onboarding.step.extension': 'Install the Shadow-AI watcher',
  'clinic.onboarding.complete': 'Looks good — your practice is set up.',
  'clinic.onboarding.skip': 'Skip for now',
  'clinic.onboarding.next': 'Next',
  'clinic.onboarding.back': 'Back',
  'clinic.onboarding.finish': 'Finish setup',

  'clinic.shadow_ai.title': 'Shadow AI watcher',
  'clinic.shadow_ai.subtitle':
    'AI tools spotted on your devices that aren’t in your registry.',
  'clinic.shadow_ai.token_label': 'Extension token',
  'clinic.shadow_ai.token_help':
    'Paste this token into the Sentinel browser extension when you install it.',
  'clinic.shadow_ai.empty': 'No unknown tools spotted in the last 30 days.',

  // ── Generic phrases ────────────────────────────────────────────────
  'common.cancel': 'Cancel',
  'common.save': 'Save',
  'common.next': 'Next',
  'common.back': 'Back',
  'common.continue': 'Continue',
  'common.loading': 'Loading…',
  'common.error': 'Something went wrong',
  'common.acknowledge': 'Acknowledge',
  'common.acknowledged': 'Acknowledged',
  'common.download': 'Download',
  'common.upgrade_plan': 'Upgrade plan',
};
