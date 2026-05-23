/**
 * Demo fixtures for VITE_MOCK_API=true builds.
 *
 * All data here is fabricated. Volumes are sized so every list page has
 * enough rows to look populated (paginated tables show 10-20 entries),
 * dashboards show meaningful aggregates, and detail pages have full
 * field coverage so nothing renders as "—" or empty state.
 */

import {
  Agent,
  AgentActivityMetrics,
  Alert,
  AuditLog,
  Policy,
  User,
  UserRole,
  DashboardMetrics,
  ModelCard,
  BiasAudit,
  DriftMeasurement,
  DriftBaseline,
  HITLReview,
  ShadowAIDetection,
  ScribeAudit,
  TransparencyRecord,
  PriorAuthRecord,
  RevenueCycleAudit,
  TechnicalFile,
  AdverseEvent,
  PMSReport,
  RiskPortfolio,
  RiskScore,
  RiskHistoryEntry,
  RiskConfiguration,
} from '@/types';

// ── Demo user (auto-login target) ──────────────────────────────────
export const demoUser: User = {
  id: 'demo-user-001',
  username: 'demo.admin',
  email: 'demo@sentinel.health',
  role: UserRole.SYSTEM_ADMIN,
  full_name: 'Demo Admin',
  is_active: true,
  organization_id: 'demo-org-001',
  tier: 'enterprise',
  created_at: '2025-01-15T09:00:00Z',
  updated_at: '2026-05-20T14:32:00Z',
  last_login: new Date().toISOString(),
};

// ── Helpers ────────────────────────────────────────────────────────
const ISO_NOW = new Date().toISOString();
const daysAgo = (n: number): string =>
  new Date(Date.now() - n * 24 * 60 * 60 * 1000).toISOString();
const hoursAgo = (n: number): string =>
  new Date(Date.now() - n * 60 * 60 * 1000).toISOString();

function paginated<T>(items: T[], page = 1, pageSize = 50) {
  const total = items.length;
  return {
    items,
    total,
    page,
    page_size: pageSize,
    total_pages: Math.max(1, Math.ceil(total / pageSize)),
  };
}

// ── Agents ─────────────────────────────────────────────────────────
export const agents: Agent[] = [
  {
    id: 'agt_radiology_assist',
    agent_id: 'agt_radiology_assist',
    name: 'Radiology Triage Assistant',
    description: 'Prioritises incoming imaging studies by acuity and routes to on-call radiologists.',
    status: 'active',
    created_at: daysAgo(180),
    last_active: hoursAgo(1),
    systems_accessed: ['PACS', 'Epic', 'RIS'],
    metadata: { team: 'Radiology', owner: 'dr.chen@hospital.org' },
  },
  {
    id: 'agt_scribe_v3',
    agent_id: 'agt_scribe_v3',
    name: 'Ambient Clinical Scribe v3',
    description: 'Transcribes encounters and drafts SOAP notes for physician sign-off.',
    status: 'active',
    created_at: daysAgo(120),
    last_active: hoursAgo(2),
    systems_accessed: ['Epic', 'Dragon'],
    metadata: { team: 'Primary Care' },
  },
  {
    id: 'agt_pa_helper',
    agent_id: 'agt_pa_helper',
    name: 'Prior Authorization Helper',
    description: 'Drafts payer prior-auth submissions from chart context.',
    status: 'active',
    created_at: daysAgo(90),
    last_active: hoursAgo(4),
    systems_accessed: ['Epic', 'Availity', 'CoverMyMeds'],
  },
  {
    id: 'agt_sepsis_alert',
    agent_id: 'agt_sepsis_alert',
    name: 'Sepsis Early Warning',
    description: 'Realtime vitals scoring with bedside alert escalation.',
    status: 'active',
    created_at: daysAgo(220),
    last_active: hoursAgo(0),
    systems_accessed: ['Epic', 'Philips IntelliVue'],
  },
  {
    id: 'agt_discharge_planner',
    agent_id: 'agt_discharge_planner',
    name: 'Discharge Planning Copilot',
    description: 'Suggests SNF/HHC placement based on diagnosis and insurance.',
    status: 'active',
    created_at: daysAgo(60),
    last_active: hoursAgo(6),
    systems_accessed: ['Epic', 'Salesforce Health Cloud'],
  },
  {
    id: 'agt_coding_assist',
    agent_id: 'agt_coding_assist',
    name: 'ICD-10 Coding Assistant',
    description: 'Suggests primary and secondary diagnosis codes from chart notes.',
    status: 'active',
    created_at: daysAgo(150),
    last_active: hoursAgo(3),
    systems_accessed: ['Epic', '3M 360'],
  },
  {
    id: 'agt_lab_anomaly',
    agent_id: 'agt_lab_anomaly',
    name: 'Lab Result Anomaly Detector',
    description: 'Flags out-of-range labs and probable lab errors before sign-off.',
    status: 'inactive',
    created_at: daysAgo(75),
    last_active: daysAgo(14),
    systems_accessed: ['Cerner Millennium', 'LabCorp'],
  },
  {
    id: 'agt_referral_router',
    agent_id: 'agt_referral_router',
    name: 'Specialist Referral Router',
    description: 'Matches referrals to in-network specialists with available slots.',
    status: 'active',
    created_at: daysAgo(30),
    last_active: hoursAgo(8),
    systems_accessed: ['Epic', 'Kyruus'],
  },
  {
    id: 'agt_med_reconcile',
    agent_id: 'agt_med_reconcile',
    name: 'Medication Reconciliation',
    description: 'Cross-checks med lists between EHRs, pharmacies and patient self-report.',
    status: 'active',
    created_at: daysAgo(45),
    last_active: hoursAgo(12),
    systems_accessed: ['Epic', 'Surescripts'],
  },
  {
    id: 'agt_no_show_predict',
    agent_id: 'agt_no_show_predict',
    name: 'Appointment No-Show Predictor',
    description: 'Predicts missed appointments and triggers automated outreach.',
    status: 'suspended',
    created_at: daysAgo(200),
    last_active: daysAgo(45),
    systems_accessed: ['Epic', 'Twilio'],
  },
];

export const agentMetrics: Record<string, AgentActivityMetrics> = Object.fromEntries(
  agents.map((a) => [
    a.id,
    {
      agent_id: a.id,
      total_actions: 1200 + Math.floor(Math.random() * 8000),
      allowed_actions: 980 + Math.floor(Math.random() * 7000),
      blocked_actions: 8 + Math.floor(Math.random() * 40),
      approval_required: 15 + Math.floor(Math.random() * 60),
      systems_accessed: a.systems_accessed ?? [],
      activity_by_day: Array.from({ length: 14 }, (_, i) => ({
        date: daysAgo(13 - i).slice(0, 10),
        count: 40 + Math.floor(Math.random() * 250),
      })),
      top_tools: [
        { tool: 'read_chart', count: 480 + Math.floor(Math.random() * 800) },
        { tool: 'write_note', count: 220 + Math.floor(Math.random() * 400) },
        { tool: 'query_labs', count: 180 + Math.floor(Math.random() * 300) },
        { tool: 'fetch_imaging', count: 90 + Math.floor(Math.random() * 200) },
        { tool: 'send_message', count: 40 + Math.floor(Math.random() * 120) },
      ],
      policy_violations: Math.floor(Math.random() * 12),
      first_seen: a.created_at,
      last_active: a.last_active,
    },
  ]),
);

// ── Policies ───────────────────────────────────────────────────────
export const policies: Policy[] = [
  {
    id: 'pol_phi_export_block',
    name: 'Block PHI export to external systems',
    description: 'Prevents any agent from exfiltrating PHI to non-allowlisted endpoints.',
    policy_type: 'data_protection',
    rules: [
      {
        id: 'r1',
        description: 'Block external HTTP egress with PHI fields',
        conditions: [
          { field: 'data_class', operator: 'contains', value: 'PHI' },
          { field: 'destination', operator: 'not_in', value: ['Epic', 'Cerner', 'Internal'] },
        ],
        action: 'block',
      },
    ],
    applies_to: ['*'],
    enabled: true,
    priority: 10,
    created_at: daysAgo(180),
    updated_at: daysAgo(12),
    created_by: 'demo.admin',
  },
  {
    id: 'pol_high_risk_med',
    name: 'Require approval for high-risk medications',
    description: 'Opioids and chemotherapy orders require attending sign-off before agent submission.',
    policy_type: 'clinical_safety',
    rules: [
      {
        id: 'r1',
        conditions: [
          { field: 'tool_name', operator: 'eq', value: 'order_medication' },
          { field: 'drug_class', operator: 'in', value: ['opioid', 'chemo', 'controlled'] },
        ],
        action: 'require_approval',
      },
    ],
    applies_to: ['agt_scribe_v3', 'agt_discharge_planner'],
    enabled: true,
    priority: 20,
    created_at: daysAgo(120),
    updated_at: daysAgo(30),
    created_by: 'cmio@hospital.org',
  },
  {
    id: 'pol_payer_cost_cap',
    name: 'Cap per-claim spend at $5,000',
    description: 'Prior-auth agents may not submit claims exceeding the configured threshold.',
    policy_type: 'financial',
    rules: [
      {
        id: 'r1',
        conditions: [
          { field: 'tool_name', operator: 'eq', value: 'submit_claim' },
          { field: 'estimated_amount_usd', operator: 'gt', value: 5000 },
        ],
        action: 'require_approval',
      },
    ],
    applies_to: ['agt_pa_helper'],
    enabled: true,
    priority: 30,
    created_at: daysAgo(60),
    created_by: 'finance@hospital.org',
  },
  {
    id: 'pol_after_hours',
    name: 'Restrict after-hours system access',
    description: 'Read-only mode for non-clinical agents between 22:00 and 06:00.',
    policy_type: 'system_access',
    rules: [
      {
        id: 'r1',
        conditions: [
          { field: 'tool_name', operator: 'in', value: ['write_note', 'order_medication'] },
          { field: 'hour_of_day', operator: 'between', value: [22, 6] },
        ],
        action: 'block',
      },
    ],
    applies_to: ['*'],
    enabled: false,
    priority: 5,
    created_at: daysAgo(15),
    created_by: 'demo.admin',
  },
  {
    id: 'pol_audit_log_immutable',
    name: 'Audit log immutability',
    description: 'Forbid any tool call that would mutate or delete audit log records.',
    policy_type: 'compliance',
    rules: [
      {
        id: 'r1',
        conditions: [
          { field: 'system_accessed', operator: 'eq', value: 'audit_log' },
          { field: 'tool_name', operator: 'in', value: ['delete', 'update'] },
        ],
        action: 'block',
      },
    ],
    applies_to: ['*'],
    enabled: true,
    priority: 100,
    created_at: daysAgo(240),
    created_by: 'system',
  },
];

// ── Audit logs ─────────────────────────────────────────────────────
const decisions: AuditLog['decision'][] = ['allowed', 'allowed', 'allowed', 'blocked', 'approved'];
export const auditLogs: AuditLog[] = Array.from({ length: 120 }, (_, i) => {
  const agent = agents[i % agents.length];
  const decision = decisions[i % decisions.length];
  return {
    id: `log_${(10000 - i).toString().padStart(5, '0')}`,
    timestamp: hoursAgo(i * 0.4),
    agent_id: agent.id,
    agent_name: agent.name,
    user_id: ['demo.admin', 'jane.doe', 'robert.kim', 'dr.chen'][i % 4],
    tool_name: ['read_chart', 'write_note', 'order_medication', 'fetch_imaging', 'submit_claim'][i % 5],
    arguments: { patient_id: `pt_${1000 + (i % 50)}`, encounter_id: `enc_${5000 + i}` },
    system_accessed: agent.systems_accessed?.[0] ?? 'Epic',
    data_touched: ['vitals', 'demographics', 'medications', 'imaging', 'labs'][i % 5],
    decision,
    policy_ids: decision !== 'allowed' ? [policies[i % policies.length].id] : [],
    reason:
      decision === 'blocked'
        ? 'Matched data-protection policy: PHI export to external destination'
        : decision === 'approved'
          ? 'Manual approval granted by attending physician'
          : undefined,
    metadata: { latency_ms: 80 + Math.floor(Math.random() * 400) },
  };
});

// ── Alerts ─────────────────────────────────────────────────────────
const alertTypes = ['policy_violation', 'high_risk_action', 'anomalous_pattern', 'auth_failure', 'data_export'];
const severities: Alert['severity'][] = ['low', 'medium', 'high', 'critical'];
export const alerts: Alert[] = Array.from({ length: 45 }, (_, i) => {
  const ack = i > 12;
  return {
    id: `alrt_${(2000 - i).toString().padStart(5, '0')}`,
    timestamp: hoursAgo(i * 1.2),
    severity: severities[i % severities.length],
    alert_type: alertTypes[i % alertTypes.length],
    agent_id: agents[i % agents.length].id,
    description: [
      'Agent attempted to write PHI to external service "Slack"',
      'High-risk medication ordered without attending review',
      'Unusual spike in chart-read volume (450% of baseline)',
      'Three consecutive auth failures from agent token',
      'Bulk export of 2,400 patient records initiated',
    ][i % 5],
    audit_log_id: auditLogs[i % auditLogs.length].id,
    acknowledged: ack,
    acknowledged_by: ack ? 'demo.admin' : null,
    acknowledged_at: ack ? hoursAgo(i * 0.5) : null,
  };
});

export const alertRules = [
  {
    id: 'rule_phi_export',
    policy_type: 'data_protection',
    alert_type: 'policy_violation',
    severity: 'critical' as const,
    conditions: { policy_id: 'pol_phi_export_block' },
    slack_webhook_url: null,
    enabled: true,
    created_at: daysAgo(180),
  },
  {
    id: 'rule_high_risk_med',
    policy_type: 'clinical_safety',
    alert_type: 'high_risk_action',
    severity: 'high' as const,
    conditions: { tool_name: 'order_medication' },
    slack_webhook_url: 'https://hooks.slack.com/services/T00/B00/REDACTED',
    enabled: true,
    created_at: daysAgo(120),
  },
  {
    id: 'rule_auth_failures',
    policy_type: null,
    alert_type: 'auth_failure',
    severity: 'medium' as const,
    conditions: { consecutive_failures_gte: 3 },
    slack_webhook_url: null,
    enabled: true,
    created_at: daysAgo(60),
  },
];

// ── Dashboard metrics ──────────────────────────────────────────────
export const dashboardMetrics: DashboardMetrics = {
  active_agents: agents.filter((a) => a.status === 'active').length,
  total_actions: 184_217,
  blocked_actions: 1_842,
  money_saved: 482_300,
  money_spent: 27_450,
  recent_alerts: alerts.slice(0, 8).map((a, i) => ({
    id: i + 1,
    timestamp: a.timestamp,
    severity: a.severity,
    alert_type: a.alert_type,
    message: a.description,
    agent_id: a.agent_id,
  })),
  top_agents: agents.slice(0, 6).map((a, i) => ({
    agent_id: a.id,
    action_count: 12_400 - i * 1_800,
  })),
  policy_violations: [
    { policy_name: 'PHI export block', count: 47 },
    { policy_name: 'High-risk medication approval', count: 23 },
    { policy_name: 'Payer cost cap', count: 18 },
    { policy_name: 'Audit log immutability', count: 6 },
    { policy_name: 'After-hours access', count: 4 },
  ],
  systems_accessed: [
    { system: 'Epic', access_count: 84_320 },
    { system: 'Cerner Millennium', access_count: 21_445 },
    { system: 'PACS', access_count: 14_870 },
    { system: 'Availity', access_count: 9_220 },
    { system: 'LabCorp', access_count: 6_180 },
    { system: 'Surescripts', access_count: 4_730 },
  ],
  activity_timeline: Array.from({ length: 24 }, (_, i) => ({
    timestamp: hoursAgo(23 - i),
    count: 200 + Math.floor(Math.sin(i / 3) * 80) + Math.floor(Math.random() * 100),
  })),
  alerts_by_severity: { low: 14, medium: 18, high: 9, critical: 4 },
  recent_blocked_actions: auditLogs
    .filter((l) => l.decision === 'blocked')
    .slice(0, 8)
    .map((l) => ({
      id: l.id,
      timestamp: l.timestamp,
      agent_id: l.agent_id,
      action: l.tool_name ?? 'unknown',
      system_accessed: l.system_accessed,
    })),
};

// ── Users ──────────────────────────────────────────────────────────
export const users: User[] = [
  demoUser,
  {
    id: 'usr_002', username: 'cmio.chen', email: 'dr.chen@hospital.org',
    role: UserRole.CMIO, full_name: 'Dr. Wei Chen', is_active: true,
    organization_id: 'demo-org-001', tier: 'enterprise',
    created_at: daysAgo(280), last_login: hoursAgo(3),
  },
  {
    id: 'usr_003', username: 'data.science', email: 'ml@hospital.org',
    role: UserRole.DATA_SCIENTIST, full_name: 'Priya Patel', is_active: true,
    organization_id: 'demo-org-001', tier: 'enterprise',
    created_at: daysAgo(220), last_login: hoursAgo(8),
  },
  {
    id: 'usr_004', username: 'compliance', email: 'compliance@hospital.org',
    role: UserRole.COMPLIANCE_OFFICER, full_name: 'Robert Kim', is_active: true,
    organization_id: 'demo-org-001', tier: 'enterprise',
    created_at: daysAgo(190), last_login: hoursAgo(24),
  },
  {
    id: 'usr_005', username: 'clinician.jane', email: 'jane.doe@hospital.org',
    role: UserRole.CLINICAL_USER, full_name: 'Jane Doe, RN', is_active: true,
    organization_id: 'demo-org-001', tier: 'enterprise',
    created_at: daysAgo(150), last_login: hoursAgo(2),
  },
  {
    id: 'usr_006', username: 'analyst.maya', email: 'maya@hospital.org',
    role: UserRole.ANALYST, full_name: 'Maya Singh', is_active: true,
    organization_id: 'demo-org-001', tier: 'enterprise',
    created_at: daysAgo(95), last_login: hoursAgo(48),
  },
  {
    id: 'usr_007', username: 'viewer.exec', email: 'ceo@hospital.org',
    role: UserRole.VIEWER, full_name: 'Eleanor Ross', is_active: true,
    organization_id: 'demo-org-001', tier: 'enterprise',
    created_at: daysAgo(45), last_login: daysAgo(7),
  },
  {
    id: 'usr_008', username: 'former.staff', email: 'former@hospital.org',
    role: UserRole.ANALYST, full_name: 'Tom Bennett', is_active: false,
    organization_id: 'demo-org-001', tier: 'enterprise',
    created_at: daysAgo(420), last_login: daysAgo(95),
  },
];

// ── Clinical: model cards ──────────────────────────────────────────
export const modelCards: ModelCard[] = [
  {
    id: 'mc_sepsis_v3', model_name: 'Sepsis Early Warning', model_version: '3.2.1',
    intended_use: 'Early identification of sepsis risk in adult ICU patients.',
    clinical_indications: 'Adults ≥18 admitted to ICU with continuous vitals monitoring.',
    contraindications: 'Pediatric, obstetric, or palliative-care patients.',
    training_data_source: 'MIMIC-IV + 4 partner hospitals (n=128,400 admissions).',
    performance_summary: 'AUROC 0.89 (95% CI 0.87-0.91); sensitivity 0.82 at 0.75 specificity.',
    bias_summary: 'Disparate impact ratio 0.94 across self-reported race subgroups.',
    fda_status: 'FDA 510(k) cleared K223481',
    lifecycle_stage: 'published', created_by: 'data.science',
    created_at: daysAgo(220), updated_at: daysAgo(15),
  },
  {
    id: 'mc_radiology_triage', model_name: 'Radiology Acuity Triage', model_version: '2.0.0',
    intended_use: 'Reorder PACS worklist by predicted acuity of head CT studies.',
    clinical_indications: 'Adult non-contrast head CT in emergency department.',
    contraindications: 'Pediatric studies and follow-up surveillance imaging.',
    training_data_source: 'Internal dataset (n=68,200 studies, 2019-2024).',
    performance_summary: 'NPV 0.97 for intracranial hemorrhage at top-25% acuity bin.',
    bias_summary: 'Performance parity verified across age and gender.',
    fda_status: 'De Novo pathway, submission Q3 2026.',
    lifecycle_stage: 'review', created_by: 'data.science',
    created_at: daysAgo(95), updated_at: daysAgo(3),
  },
  {
    id: 'mc_scribe', model_name: 'Ambient Clinical Scribe', model_version: '3.4.2',
    intended_use: 'Transcribe encounters and draft SOAP notes from audio.',
    clinical_indications: 'Outpatient primary-care and specialty visits in English.',
    contraindications: 'Behavioral-health sessions; non-English encounters.',
    training_data_source: 'Vendor-provided + 12k consented encounters.',
    performance_summary: 'WER 4.1%; ICD-10 suggestion precision 0.86.',
    bias_summary: 'WER variance ±0.7% across regional accent groups.',
    fda_status: 'Non-device CDS exemption (21st Century Cures Act).',
    lifecycle_stage: 'published', created_by: 'data.science',
    created_at: daysAgo(160), updated_at: daysAgo(28),
  },
  {
    id: 'mc_readmit', model_name: '30-Day Readmission Risk', model_version: '1.5.0',
    intended_use: 'Stratify discharge patients by 30-day readmission probability.',
    clinical_indications: 'Adult inpatient discharges to home or SNF.',
    training_data_source: 'Internal claims + EHR (n=412,000 discharges).',
    performance_summary: 'AUROC 0.74; calibration intercept 0.02.',
    bias_summary: 'Calibration drift detected in <65 cohort; recalibrated 2026-03.',
    fda_status: 'Not a medical device.',
    lifecycle_stage: 'published', created_by: 'data.science',
    created_at: daysAgo(310), updated_at: daysAgo(60),
  },
  {
    id: 'mc_chemo_dose', model_name: 'Chemo Dose Verification', model_version: '0.4.0',
    intended_use: 'Cross-check ordered chemotherapy dose against protocol.',
    clinical_indications: 'Oncology infusion orders for adult solid tumors.',
    training_data_source: 'Vendor + internal protocols (n=18,200 regimens).',
    performance_summary: 'Detection rate for known dose-error patterns: 0.97.',
    bias_summary: 'Pending — bias audit scheduled for v0.5.',
    fda_status: 'Pre-submission Q-Sub in progress.',
    lifecycle_stage: 'draft', created_by: 'data.science',
    created_at: daysAgo(40), updated_at: daysAgo(2),
  },
];

// ── Clinical: bias audits ──────────────────────────────────────────
export const biasAudits: BiasAudit[] = [
  { id: 'ba_001', model_card_id: 'mc_sepsis_v3', status: 'completed', subgroups: ['race', 'sex', 'age_band'], overall_score: 0.94, disparate_impact_ratio: 0.94, findings_summary: 'Parity within ±5% across all subgroups. No statistically significant disparate impact.', created_by: 'data.science', created_at: daysAgo(45), completed_at: daysAgo(44) },
  { id: 'ba_002', model_card_id: 'mc_radiology_triage', status: 'completed', subgroups: ['sex', 'age_band'], overall_score: 0.97, disparate_impact_ratio: 0.97, findings_summary: 'Performance parity verified. NPV variance <1.5% across subgroups.', created_by: 'data.science', created_at: daysAgo(30), completed_at: daysAgo(29) },
  { id: 'ba_003', model_card_id: 'mc_scribe', status: 'completed', subgroups: ['accent_region', 'sex'], overall_score: 0.91, disparate_impact_ratio: 0.91, findings_summary: 'WER 0.7% higher for South-Asian English accent — within acceptable tolerance, retraining set updated.', created_by: 'data.science', created_at: daysAgo(60), completed_at: daysAgo(59) },
  { id: 'ba_004', model_card_id: 'mc_readmit', status: 'completed', subgroups: ['race', 'insurance_type', 'age_band'], overall_score: 0.82, disparate_impact_ratio: 0.82, findings_summary: 'Calibration drift detected in Medicaid + <65 cohort. Recalibrated.', created_by: 'data.science', created_at: daysAgo(75), completed_at: daysAgo(74) },
  { id: 'ba_005', model_card_id: 'mc_chemo_dose', status: 'pending', subgroups: ['cancer_type', 'sex'], created_by: 'data.science', created_at: daysAgo(5) },
  { id: 'ba_006', model_card_id: 'mc_sepsis_v3', status: 'running', subgroups: ['race', 'sex', 'age_band', 'insurance_type'], created_by: 'data.science', created_at: hoursAgo(2) },
];

// ── Clinical: drift ────────────────────────────────────────────────
export const driftMeasurements: DriftMeasurement[] = [
  { id: 'dm_001', baseline_id: 'dbl_001', psi_score: 0.08, ks_statistic: 0.04, status: 'ok', measured_at: hoursAgo(2) },
  { id: 'dm_002', baseline_id: 'dbl_002', psi_score: 0.14, ks_statistic: 0.09, status: 'warning', measured_at: hoursAgo(4) },
  { id: 'dm_003', baseline_id: 'dbl_003', psi_score: 0.27, ks_statistic: 0.18, status: 'alert', measured_at: hoursAgo(6) },
  { id: 'dm_004', baseline_id: 'dbl_004', psi_score: 0.05, ks_statistic: 0.02, status: 'ok', measured_at: hoursAgo(8) },
  { id: 'dm_005', baseline_id: 'dbl_001', psi_score: 0.11, ks_statistic: 0.06, status: 'warning', measured_at: daysAgo(1) },
  { id: 'dm_006', baseline_id: 'dbl_003', psi_score: 0.31, ks_statistic: 0.21, status: 'alert', measured_at: daysAgo(2) },
];

export const driftBaselines: DriftBaseline[] = [
  { id: 'dbl_001', model_card_id: 'mc_sepsis_v3', feature_name: 'heart_rate', baseline_mean: 82.3, baseline_std: 14.2, created_at: daysAgo(200) },
  { id: 'dbl_002', model_card_id: 'mc_sepsis_v3', feature_name: 'lactate', baseline_mean: 1.8, baseline_std: 0.9, created_at: daysAgo(200) },
  { id: 'dbl_003', model_card_id: 'mc_readmit', feature_name: 'length_of_stay_days', baseline_mean: 4.2, baseline_std: 2.7, created_at: daysAgo(310) },
  { id: 'dbl_004', model_card_id: 'mc_scribe', feature_name: 'audio_snr_db', baseline_mean: 38.1, baseline_std: 6.4, created_at: daysAgo(160) },
];

// ── Clinical: HITL reviews ─────────────────────────────────────────
export const hitlReviews: HITLReview[] = Array.from({ length: 28 }, (_, i) => {
  const statuses: HITLReview['status'][] = ['pending', 'pending', 'pending', 'approved', 'rejected', 'modified'];
  const status = statuses[i % statuses.length];
  return {
    id: `hitl_${(500 - i).toString().padStart(4, '0')}`,
    model_id: modelCards[i % modelCards.length].id,
    ai_decision: [
      'Recommend admission to ICU',
      'Discharge to home with follow-up in 7 days',
      'Initiate empiric broad-spectrum antibiotics',
      'Order CT abdomen with contrast',
      'Transition to comfort-focused care',
    ][i % 5],
    ai_confidence: 0.62 + (i % 7) * 0.05,
    risk_score: 0.3 + (i % 9) * 0.07,
    status,
    reviewer_id: status !== 'pending' ? users[1 + (i % 4)].id : undefined,
    reviewer_decision: status !== 'pending'
      ? ['Concur with AI recommendation', 'Modified: reduce dose by 25%', 'Override: patient declined', 'Concur'][i % 4]
      : undefined,
    reviewer_notes: status !== 'pending'
      ? 'Reviewed in context of full chart and recent imaging. See encounter note for full reasoning.'
      : undefined,
    reviewed_at: status !== 'pending' ? hoursAgo(i * 0.8) : undefined,
    sla_deadline: status === 'pending' ? hoursAgo(-(2 + (i % 6))) : undefined,
    created_at: hoursAgo(i * 1.5 + 1),
  };
});

// ── Admin: Shadow AI ───────────────────────────────────────────────
export const shadowAIDetections: ShadowAIDetection[] = [
  { id: 'sai_001', detected_tool: 'ChatGPT (consumer)', endpoint_domain: 'chat.openai.com', staff_ip: '10.20.4.118', hipaa_risk: true, severity: 'critical', detected_at: hoursAgo(2), allowlisted: false },
  { id: 'sai_002', detected_tool: 'Claude.ai (consumer)', endpoint_domain: 'claude.ai', staff_ip: '10.20.4.92', hipaa_risk: true, severity: 'high', detected_at: hoursAgo(8), allowlisted: false },
  { id: 'sai_003', detected_tool: 'Gemini Web', endpoint_domain: 'gemini.google.com', staff_ip: '10.20.7.41', hipaa_risk: true, severity: 'high', detected_at: hoursAgo(14), allowlisted: false },
  { id: 'sai_004', detected_tool: 'GitHub Copilot (personal)', endpoint_domain: 'api.githubcopilot.com', staff_ip: '10.20.4.55', hipaa_risk: false, severity: 'medium', detected_at: daysAgo(1), allowlisted: true },
  { id: 'sai_005', detected_tool: 'Perplexity', endpoint_domain: 'www.perplexity.ai', staff_ip: '10.20.9.12', hipaa_risk: false, severity: 'low', detected_at: daysAgo(2), allowlisted: false },
  { id: 'sai_006', detected_tool: 'Notion AI', endpoint_domain: 'api.notion.com', staff_ip: '10.20.6.77', hipaa_risk: true, severity: 'medium', detected_at: daysAgo(3), allowlisted: false },
  { id: 'sai_007', detected_tool: 'Grammarly (free)', endpoint_domain: 'api.grammarly.com', staff_ip: '10.20.4.118', hipaa_risk: true, severity: 'high', detected_at: daysAgo(4), allowlisted: false },
];

// ── Admin: Scribe audits ───────────────────────────────────────────
export const scribeAudits: ScribeAudit[] = Array.from({ length: 22 }, (_, i) => {
  const statuses: ScribeAudit['status'][] = ['pass', 'pass', 'pass', 'warning', 'fail'];
  const status = statuses[i % statuses.length];
  return {
    id: `sa_${(300 - i).toString().padStart(4, '0')}`,
    encounter_id: `enc_${20000 + i}`,
    completeness_score: status === 'pass' ? 0.92 + Math.random() * 0.08 : status === 'warning' ? 0.78 + Math.random() * 0.1 : 0.55 + Math.random() * 0.15,
    hallucination_detected: status === 'fail',
    icd10_accuracy: 0.78 + Math.random() * 0.2,
    status,
    findings_count: status === 'pass' ? 0 : status === 'warning' ? 1 + (i % 3) : 3 + (i % 4),
    audited_at: hoursAgo(i * 3),
  };
});

// ── Admin: Transparency ────────────────────────────────────────────
export const transparencyRecords: TransparencyRecord[] = modelCards.map((mc, i) => ({
  id: `tr_${(i + 1).toString().padStart(3, '0')}`,
  algorithm_name: mc.model_name,
  plain_language_summary: `${mc.model_name} helps clinicians by ${mc.intended_use.toLowerCase()} It is intended for ${mc.clinical_indications.toLowerCase()}`,
  evidence_base: mc.performance_summary,
  version: 1 + (i % 3),
  published_at: mc.lifecycle_stage === 'published' ? daysAgo(20 + i * 10) : undefined,
  created_at: daysAgo(30 + i * 10),
}));

// ── Finance: Prior auth ────────────────────────────────────────────
export const priorAuthRecords: PriorAuthRecord[] = Array.from({ length: 35 }, (_, i) => {
  const recs = ['approve', 'deny', 'pend_for_info'];
  const services = ['MRI lumbar spine', 'PT 12 visits', 'Tier-3 specialty drug', 'CT abdomen', 'Sleep study'];
  return {
    id: `pa_${(700 - i).toString().padStart(4, '0')}`,
    claim_id: `clm_${4000 + i}`,
    service_type: services[i % services.length],
    ai_recommendation: recs[i % recs.length],
    ai_confidence: 0.7 + (i % 5) * 0.05,
    final_decision: recs[(i + 1) % recs.length],
    denial_reason_code: i % 3 === 0 ? 'CO-50 (medical necessity)' : undefined,
    record_hash: `0x${(0xabcdef00 + i).toString(16)}`,
    prev_record_hash: `0x${(0xabcdef00 + i - 1).toString(16)}`,
    created_at: hoursAgo(i * 2),
  };
});

// ── Finance: Revenue cycle ─────────────────────────────────────────
export const revenueCycleAudits: RevenueCycleAudit[] = Array.from({ length: 24 }, (_, i) => ({
  id: `rc_${(400 - i).toString().padStart(4, '0')}`,
  claim_id: `clm_${5000 + i}`,
  risk_score: 0.1 + (i % 10) * 0.09,
  upcoding_flags: i % 7 === 0 ? 1 + (i % 3) : 0,
  unbundling_flags: i % 5 === 0 ? 1 : 0,
  modifier_flags: i % 4 === 0 ? 1 + (i % 2) : 0,
  recommendation: i % 8 === 0 ? 'Hold for coder review' : 'Submit as coded',
  audited_at: hoursAgo(i * 4),
}));

// ── Regulatory: Technical files ────────────────────────────────────
export const technicalFiles: TechnicalFile[] = [
  { id: 'tf_001', title: 'Sepsis EWS — FDA 510(k)', regulatory_type: 'fda_510k', product_name: 'Sepsis Early Warning', device_version: '3.2.1', lifecycle_stage: 'approved', created_by: 'compliance', created_at: daysAgo(420), updated_at: daysAgo(30) },
  { id: 'tf_002', title: 'Radiology Triage — De Novo', regulatory_type: 'fda_510k', product_name: 'Radiology Acuity Triage', device_version: '2.0.0', lifecycle_stage: 'under_review', created_by: 'compliance', created_at: daysAgo(180), updated_at: daysAgo(5) },
  { id: 'tf_003', title: 'Sepsis EWS — EU MDR Class IIa', regulatory_type: 'eu_mdr', product_name: 'Sepsis Early Warning', device_version: '3.2.1', lifecycle_stage: 'submitted', created_by: 'compliance', created_at: daysAgo(150), updated_at: daysAgo(12) },
  { id: 'tf_004', title: 'Chemo Dose Verification — pre-sub', regulatory_type: 'both', product_name: 'Chemo Dose Verification', device_version: '0.4.0', lifecycle_stage: 'draft', created_by: 'compliance', created_at: daysAgo(40), updated_at: hoursAgo(18) },
  { id: 'tf_005', title: 'Scribe v2 — retired filings', regulatory_type: 'fda_510k', product_name: 'Ambient Scribe', device_version: '2.0.0', lifecycle_stage: 'retired', created_by: 'compliance', created_at: daysAgo(900), updated_at: daysAgo(300) },
];

// ── Regulatory: Adverse events ─────────────────────────────────────
export const adverseEvents: AdverseEvent[] = [
  { id: 'ae_001', model_id: 'mc_sepsis_v3', agent_id: 'agt_sepsis_alert', event_type: 'False negative', severity: 'high', description: 'Patient developed septic shock 6 hours after model assigned low-risk score.', patient_impact: 'ICU admission, no mortality.', status: 'investigating', reported_at: daysAgo(8), created_at: daysAgo(8) },
  { id: 'ae_002', model_id: 'mc_readmit', event_type: 'Demographic disparity', severity: 'medium', description: 'Higher false-positive rate in Medicaid <65 cohort flagged by analyst.', status: 'resolved', reported_at: daysAgo(60), resolved_at: daysAgo(35), created_at: daysAgo(60) },
  { id: 'ae_003', model_id: 'mc_scribe', event_type: 'Hallucinated medication', severity: 'critical', description: 'Scribe drafted a note referencing a medication never discussed in encounter. Caught at sign-off.', patient_impact: 'None — caught before signing.', status: 'reported_to_fda', reported_at: daysAgo(22), resolved_at: daysAgo(15), created_at: daysAgo(22) },
  { id: 'ae_004', model_id: 'mc_radiology_triage', event_type: 'Worklist mis-prioritization', severity: 'low', description: 'Routine follow-up CT was triaged ahead of stat ED study.', status: 'open', reported_at: daysAgo(3), created_at: daysAgo(3) },
  { id: 'ae_005', model_id: 'mc_chemo_dose', event_type: 'Edge-case protocol miss', severity: 'medium', description: 'Pediatric dosing edge case not flagged (out of indication, pre-launch test data).', status: 'investigating', reported_at: daysAgo(1), created_at: daysAgo(1) },
];

// ── Regulatory: PMS reports ────────────────────────────────────────
export const pmsReports: PMSReport[] = [
  { id: 'pms_001', report_type: 'psur', status: 'submitted', period_start: '2025-01-01', period_end: '2026-01-01', summary: 'PSUR 2025 — all post-market signals reviewed, no new safety signals identified.', generated_at: daysAgo(80), created_by: 'compliance', created_at: daysAgo(85) },
  { id: 'pms_002', report_type: 'mdr', status: 'submitted', period_start: '2026-01-01', period_end: '2026-04-01', summary: 'MDR Q1 2026 — 1 reportable event (hallucinated medication, mitigated).', generated_at: daysAgo(50), created_by: 'compliance', created_at: daysAgo(55) },
  { id: 'pms_003', report_type: 'quarterly', status: 'published', period_start: '2026-04-01', period_end: '2026-07-01', summary: 'Q2 internal performance summary across all deployed models.', generated_at: daysAgo(10), created_by: 'compliance', created_at: daysAgo(12) },
  { id: 'pms_004', report_type: 'incident', status: 'draft', period_start: '2026-05-15', period_end: '2026-05-22', created_by: 'compliance', created_at: daysAgo(2) },
];

// ── Risk ───────────────────────────────────────────────────────────
export const riskPortfolio: RiskPortfolio = {
  total_models: modelCards.length,
  avg_risk: 42.8,
  by_risk_level: { low: 2, medium: 2, high: 1, critical: 0 },
  models: modelCards.map((mc, i) => ({
    model_id: mc.id,
    total_risk: [28, 51, 35, 62, 38][i],
    risk_level: (['low', 'medium', 'medium', 'high', 'medium'] as const)[i],
    trend: (['stable', 'up', 'down', 'up', 'stable'] as const)[i],
    computed_at: hoursAgo(i * 2),
  })),
};

export const riskScores: Record<string, RiskScore> = Object.fromEntries(
  modelCards.map((mc, i) => [
    mc.id,
    {
      id: `rs_${i + 1}`,
      model_id: mc.id,
      severity_score: [22, 48, 30, 65, 35][i],
      exposure_score: [18, 42, 28, 55, 30][i],
      regulatory_penalty: [12, 38, 22, 60, 25][i],
      total_risk: [28, 51, 35, 62, 38][i],
      risk_level: (['low', 'medium', 'medium', 'high', 'medium'] as const)[i],
      severity_factors: { clinical_impact: 0.4, blast_radius: 0.3, reversibility: 0.2, time_to_detect: 0.1 },
      exposure_factors: { user_count: 0.3, transaction_volume: 0.4, data_sensitivity: 0.3 },
      regulatory_flags: { fda: i < 3, eu_mdr: i < 2, hipaa: true, gdpr: i < 2 },
      org_multiplier: 1.1,
      computed_at: hoursAgo(i * 2),
    },
  ]),
);

export const riskHistory: Record<string, RiskHistoryEntry[]> = Object.fromEntries(
  modelCards.map((mc) => [
    mc.id,
    Array.from({ length: 12 }, (_, i) => {
      const tot = 30 + Math.floor(Math.sin(i / 2) * 15) + Math.floor(Math.random() * 10);
      return {
        id: `rh_${mc.id}_${i}`,
        model_id: mc.id,
        total_risk: tot,
        risk_level: tot > 60 ? ('high' as const) : tot > 40 ? ('medium' as const) : ('low' as const),
        delta: i === 0 ? undefined : (Math.random() - 0.5) * 8,
        trend: (['up', 'down', 'stable'] as const)[i % 3],
        computed_at: daysAgo(60 - i * 5),
      };
    }),
  ]),
);

export const riskConfiguration: RiskConfiguration = {
  id: 'rc_default',
  regulatory_multiplier: 1.25,
  critical_threshold: 75,
  high_threshold: 55,
  medium_threshold: 35,
};

// ── Organization ───────────────────────────────────────────────────
export const organization = {
  id: 'demo-org-001',
  name: 'Demo Health System',
  slug: 'demo-health',
  org_type: 'integrated_delivery_network',
  hipaa_baa_signed: true,
  hipaa_baa_date: daysAgo(180).slice(0, 10),
  is_active: true,
};

// ── CHAI compliance / related artifacts (model card detail) ────────
export const chaiCompliance = (cardId: string) => ({
  card_id: cardId,
  score: 11,
  total: 14,
  percent: 78.5,
  sections: [
    { key: 'intended_use', label: 'Intended use', status: 'complete' as const },
    { key: 'training_data', label: 'Training data source', status: 'complete' as const },
    { key: 'performance', label: 'Performance metrics', status: 'complete' as const },
    { key: 'bias_assessment', label: 'Bias / fairness assessment', status: 'complete' as const },
    { key: 'drift_monitoring', label: 'Drift monitoring plan', status: 'partial' as const, detail: 'Plan documented; thresholds need clinical sign-off.' },
    { key: 'human_oversight', label: 'Human oversight design', status: 'complete' as const },
    { key: 'patient_facing', label: 'Patient-facing disclosure', status: 'missing' as const, detail: 'Required for published lifecycle stage.' },
  ],
  publishable: false,
  blockers: ['Add patient-facing disclosure', 'Finalize drift thresholds'],
});

export const relatedArtifacts = (cardId: string) => ({
  card_id: cardId,
  bias_audits: biasAudits
    .filter((b) => b.model_card_id === cardId)
    .map((b) => ({ kind: 'bias_audit', id: b.id, title: `Bias audit ${b.id}`, status: b.status, timestamp: b.created_at })),
  drift_baselines: driftBaselines
    .filter((d) => d.model_card_id === cardId)
    .map((d) => ({ kind: 'drift_baseline', id: d.id, title: d.feature_name, timestamp: d.created_at })),
  drift_alerts: driftMeasurements
    .filter((m) => m.status !== 'ok')
    .slice(0, 3)
    .map((m) => ({ kind: 'drift_alert', id: m.id, title: `PSI ${m.psi_score.toFixed(2)}`, severity: m.status, timestamp: m.measured_at })),
  adverse_events: adverseEvents
    .filter((a) => a.model_id === cardId)
    .map((a) => ({ kind: 'adverse_event', id: a.id, title: a.event_type, severity: a.severity, timestamp: a.reported_at })),
  risk_scores: riskScores[cardId]
    ? [{ kind: 'risk_score', id: riskScores[cardId].id, title: `Total risk ${riskScores[cardId].total_risk}`, severity: riskScores[cardId].risk_level, timestamp: riskScores[cardId].computed_at }]
    : [],
  transparency_records: transparencyRecords
    .filter((t) => t.algorithm_name === modelCards.find((mc) => mc.id === cardId)?.model_name)
    .map((t) => ({ kind: 'transparency', id: t.id, title: `v${t.version}`, timestamp: t.created_at })),
});

// ── Export pre-paginated helpers ───────────────────────────────────
export { paginated, ISO_NOW };
