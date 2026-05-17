// ============================================================
// User and Authentication Types
// ============================================================

export enum UserRole {
  SYSTEM_ADMIN = 'system_admin',
  ADMIN = 'admin',          // ORG_ADMIN — kept as 'admin' for backend compat
  CMIO = 'cmio',
  DATA_SCIENTIST = 'data_scientist',
  COMPLIANCE_OFFICER = 'compliance_officer',
  CLINICAL_USER = 'clinical_user',
  ANALYST = 'analyst',
  VIEWER = 'viewer',
}

// ────────────────────────────────────────────────────────────────────
// Product tier — selects the dashboard persona (hospital vs clinic).
// "enterprise" preserves the legacy hospital-first experience for every
// pre-clinic customer.  Three "clinic_*" tiers are SMB SKUs.
// ────────────────────────────────────────────────────────────────────
export type TierKey =
  | 'enterprise'
  | 'clinic_basic'
  | 'clinic_standard'
  | 'clinic_multi_site';

export const CLINIC_TIERS: TierKey[] = [
  'clinic_basic',
  'clinic_standard',
  'clinic_multi_site',
];

export const isClinicTier = (tier: TierKey | null | undefined): boolean =>
  tier !== null && tier !== undefined && (CLINIC_TIERS as string[]).includes(tier);

const KNOWN_TIERS = new Set<string>(['enterprise', ...CLINIC_TIERS]);

/**
 * HIGH-026 — Runtime-validate an arbitrary value into a TierKey.
 *
 * Replaces the unsafe `(raw as TierKey)` casts at AuthContext.tsx:184 and
 * AppLayout.tsx:121-122. Any value outside the four canonical tiers
 * collapses to 'enterprise', which keeps the historical default behaviour
 * for unrecognised or null inputs without quietly disabling tier checks.
 */
export const resolveTier = (raw: unknown): TierKey => {
  if (typeof raw !== 'string') return 'enterprise';
  return KNOWN_TIERS.has(raw) ? (raw as TierKey) : 'enterprise';
};

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  full_name?: string;
  is_active: boolean;
  organization_id?: string;
  tier?: TierKey;
  created_at: string;
  updated_at?: string;
  last_login?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// ============================================================
// Agent Types
// ============================================================

export interface Agent {
  id: string;
  agent_id?: string;
  name: string;
  description?: string;
  status: 'active' | 'inactive' | 'suspended';
  created_at: string;
  last_active?: string;
  systems_accessed?: string[];
  metadata?: Record<string, unknown>;
}

export interface AgentListResponse {
  agents: Agent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AgentActivityMetrics {
  agent_id: string;
  total_actions: number;
  allowed_actions: number;
  blocked_actions: number;
  approval_required: number;
  systems_accessed: string[];
  activity_by_day: Array<{ date: string; count: number }>;
  top_tools: Array<{ tool: string; count: number }>;
  policy_violations: number;
  first_seen: string;
  last_active?: string;
}

// ============================================================
// Policy Types
// ============================================================

export interface Policy {
  id: string;
  name: string;
  description?: string;
  policy_type: string;
  rules: PolicyRule[];
  applies_to: string[];
  enabled: boolean;
  priority?: number;
  created_at: string;
  updated_at?: string;
  created_by?: string;
}

export interface PolicyRule {
  id?: string;
  description?: string;
  conditions: PolicyCondition[];
  action: 'allow' | 'block' | 'require_approval';
  metadata?: Record<string, unknown>;
}

export interface PolicyCondition {
  field: string;
  operator: string;
  value: unknown;
}

export interface PolicyCreate {
  name: string;
  description?: string;
  policy_type: string;
  rules: PolicyRule[];
  applies_to: string[];
  enabled?: boolean;
  priority?: number;
}

export interface PolicyUpdate {
  name?: string;
  description?: string;
  policy_type?: string;
  rules?: PolicyRule[];
  applies_to?: string[];
  enabled?: boolean;
  priority?: number;
}

export interface PolicyListResponse {
  policies: Policy[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ============================================================
// Audit Log Types
// ============================================================

export interface AuditLog {
  id: string;
  timestamp: string;
  agent_id: string;
  agent_name?: string;
  user_id?: string;
  tool_name?: string;
  arguments?: Record<string, unknown>;
  system_accessed: string;
  data_touched?: string;
  decision: 'allowed' | 'blocked' | 'approved';
  policy_ids?: string[];
  reason?: string;
  metadata?: Record<string, unknown>;
}

export interface AuditLogListResponse {
  logs: AuditLog[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ============================================================
// Alert Types
// ============================================================

export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface Alert {
  id: string;
  timestamp: string;
  severity: AlertSeverity;
  alert_type: string;
  agent_id: string;
  description: string;
  audit_log_id: string | null;
  acknowledged: boolean;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
}

export interface AlertRule {
  id: string;
  policy_type: string | null;
  alert_type: string;
  severity: AlertSeverity;
  conditions: Record<string, unknown> | null;
  slack_webhook_url: string | null;
  enabled: boolean;
  created_at: string;
}

// ============================================================
// Dashboard Metrics
// ============================================================

export interface DashboardMetrics {
  active_agents: number;
  total_actions: number;
  blocked_actions: number;
  money_saved: number;
  money_spent: number;
  recent_alerts: Array<{
    id: number;
    timestamp: string;
    severity: string;
    alert_type: string;
    message: string;
    agent_id?: string;
  }>;
  top_agents: Array<{ agent_id: string; action_count: number }>;
  policy_violations: Array<{ policy_name: string; count: number }>;
  systems_accessed: Array<{ system: string; access_count: number }>;
  activity_timeline: Array<{ timestamp: string; count: number }>;
  alerts_by_severity: Record<string, number>;
  recent_blocked_actions: Array<{
    id: string;
    timestamp: string;
    agent_id: string;
    action: string;
    system_accessed: string;
  }>;
}

// ============================================================
// Clinical Types
// ============================================================

export type ModelCardLifecycle = 'draft' | 'review' | 'published' | 'retired';

export interface ModelCard {
  id: string;
  organization_id?: string;
  model_name: string;
  model_version: string;
  intended_use: string;
  clinical_indications: string;
  contraindications?: string;
  training_data_source?: string;
  performance_summary?: string;
  bias_summary?: string;
  fda_status?: string;
  lifecycle_stage: ModelCardLifecycle;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export type BiasAuditStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface BiasAudit {
  id: string;
  organization_id?: string;
  model_card_id: string;
  status: BiasAuditStatus;
  subgroups: string[];
  overall_score?: number;
  disparate_impact_ratio?: number;
  findings_summary?: string;
  created_by?: string;
  created_at: string;
  completed_at?: string;
}

export type DriftStatus = 'ok' | 'warning' | 'alert';

export interface DriftBaseline {
  id: string;
  model_card_id: string;
  organization_id?: string;
  feature_name: string;
  baseline_mean: number;
  baseline_std: number;
  created_at: string;
}

export interface DriftMeasurement {
  id: string;
  baseline_id: string;
  psi_score: number;
  ks_statistic?: number;
  status: DriftStatus;
  measured_at: string;
}

export type HITLStatus = 'pending' | 'approved' | 'rejected' | 'modified';

export interface HITLReview {
  id: string;
  organization_id?: string;
  model_id: string;
  ai_decision: string;
  ai_confidence?: number;
  risk_score?: number;
  status: HITLStatus;
  reviewer_id?: string;
  reviewer_decision?: string;
  reviewer_notes?: string;
  reviewed_at?: string;
  sla_deadline?: string;
  created_at: string;
}

// ============================================================
// Administrative Governance Types
// ============================================================

export type ShadowAISeverity = 'low' | 'medium' | 'high' | 'critical';

export interface ShadowAIDetection {
  id: string;
  organization_id?: string;
  detected_tool: string;
  endpoint_domain: string;
  staff_ip?: string;
  hipaa_risk: boolean;
  severity: ShadowAISeverity;
  detected_at: string;
  allowlisted: boolean;
}

export type ScribeAuditStatus = 'pass' | 'warning' | 'fail';

export interface ScribeAudit {
  id: string;
  organization_id?: string;
  encounter_id: string;
  completeness_score: number;
  hallucination_detected: boolean;
  icd10_accuracy?: number;
  status: ScribeAuditStatus;
  findings_count: number;
  audited_at: string;
}

export interface TransparencyRecord {
  id: string;
  organization_id?: string;
  algorithm_name: string;
  plain_language_summary: string;
  evidence_base?: string;
  version: number;
  published_at?: string;
  created_at: string;
}

// ============================================================
// Financial & Payer Governance Types
// ============================================================

export interface PriorAuthRecord {
  id: string;
  organization_id?: string;
  claim_id: string;
  service_type?: string;
  ai_recommendation: string;
  ai_confidence: number;
  final_decision: string;
  denial_reason_code?: string;
  record_hash: string;
  prev_record_hash: string;
  created_at: string;
}

export interface RevenueCycleAudit {
  id: string;
  organization_id?: string;
  claim_id: string;
  risk_score: number;
  upcoding_flags: number;
  unbundling_flags: number;
  modifier_flags: number;
  recommendation: string;
  audited_at: string;
}

// ============================================================
// Regulatory / MedTech Types
// ============================================================

export type TechnicalFileLifecycle = 'draft' | 'submitted' | 'under_review' | 'approved' | 'retired';
export type RegulatoryType = 'fda_510k' | 'eu_mdr' | 'both';

export interface TechnicalFile {
  id: string;
  organization_id?: string;
  title: string;
  regulatory_type: RegulatoryType;
  product_name: string;
  device_version: string;
  lifecycle_stage: TechnicalFileLifecycle;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export type AdverseEventSeverity = 'low' | 'medium' | 'high' | 'critical';
export type AdverseEventStatus = 'open' | 'investigating' | 'resolved' | 'reported_to_fda';

export interface AdverseEvent {
  id: string;
  organization_id?: string;
  model_id: string;
  agent_id?: string;
  event_type: string;
  severity: AdverseEventSeverity;
  description: string;
  patient_impact?: string;
  status: AdverseEventStatus;
  reported_at: string;
  resolved_at?: string;
  created_at: string;
}

export type PMSReportType = 'psur' | 'mdr' | 'incident' | 'quarterly';
export type PMSReportStatus = 'draft' | 'published' | 'submitted';

export interface PMSReport {
  id: string;
  organization_id?: string;
  report_type: PMSReportType;
  status: PMSReportStatus;
  period_start: string;
  period_end: string;
  summary?: string;
  generated_at?: string;
  created_by?: string;
  created_at: string;
}

// ============================================================
// Risk Scoring Types
// ============================================================

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type RiskTrend = 'up' | 'down' | 'stable';

export interface RiskScore {
  id: string;
  organization_id?: string;
  model_id: string;
  agent_id?: string;
  severity_score: number;
  exposure_score: number;
  regulatory_penalty: number;
  total_risk: number;
  risk_level: RiskLevel;
  severity_factors: Record<string, number>;
  exposure_factors: Record<string, number>;
  regulatory_flags: Record<string, boolean>;
  org_multiplier: number;
  computed_at: string;
}

export interface RiskHistoryEntry {
  id: string;
  model_id: string;
  total_risk: number;
  risk_level: RiskLevel;
  delta?: number;
  trend: RiskTrend;
  computed_at: string;
}

export interface RiskPortfolioModel {
  model_id: string;
  total_risk: number;
  risk_level: RiskLevel;
  trend: RiskTrend;
  computed_at: string;
}

export interface RiskPortfolio {
  total_models: number;
  avg_risk: number;
  by_risk_level: Record<RiskLevel, number>;
  models: RiskPortfolioModel[];
}

export interface RiskConfiguration {
  id: string;
  organization_id?: string;
  regulatory_multiplier: number;
  critical_threshold: number;
  high_threshold: number;
  medium_threshold: number;
}

// ============================================================
// Shared / Utility Types
// ============================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}
