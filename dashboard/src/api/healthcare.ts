// src/api/healthcare.ts
import { apiClient } from '@/api/client';
import {
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
  PaginatedResponse,
} from '@/types';

/**
 * Normalise list responses.
 *
 * Some Sentinel list endpoints return a bare array, others return a
 * `PaginatedResponse<T>`. The dashboard pages all expect the paginated
 * shape (`{ items, total, page, page_size, total_pages }`), so this helper
 * coerces both forms into the same envelope. Without this, bare-array
 * responses produce `data.items === undefined`, which the pages render as
 * empty state — the bug that was hiding every dashboard's data.
 */
function toPaginated<T>(
  raw: T[] | PaginatedResponse<T> | null | undefined,
  page = 1,
  pageSize = 100,
): PaginatedResponse<T> {
  if (Array.isArray(raw)) {
    return {
      items: raw,
      total: raw.length,
      page,
      page_size: pageSize,
      total_pages: Math.max(1, Math.ceil(raw.length / Math.max(1, pageSize))),
    };
  }
  if (raw && Array.isArray((raw as PaginatedResponse<T>).items)) {
    const r = raw as PaginatedResponse<T>;
    return {
      items: r.items,
      total: typeof r.total === 'number' ? r.total : r.items.length,
      page: r.page ?? page,
      page_size: r.page_size ?? pageSize,
      total_pages:
        r.total_pages ??
        Math.max(1, Math.ceil((r.total ?? r.items.length) / Math.max(1, r.page_size ?? pageSize))),
    };
  }
  return {
    items: [],
    total: 0,
    page,
    page_size: pageSize,
    total_pages: 1,
  };
}

// ============================================================
// Model Cards
// ============================================================

export async function listModelCards(params?: {
  lifecycle_stage?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<ModelCard>> {
  const raw = await apiClient.get<ModelCard[] | PaginatedResponse<ModelCard>>(
    '/v1/clinical/model-cards',
    params,
  );
  return toPaginated<ModelCard>(raw, params?.page, params?.page_size);
}

export async function getModelCard(id: string): Promise<ModelCard> {
  return apiClient.get<ModelCard>(`/v1/clinical/model-cards/${id}`);
}

export async function createModelCard(
  data: Omit<ModelCard, 'id' | 'created_at' | 'updated_at' | 'created_by'>
): Promise<ModelCard> {
  return apiClient.post<ModelCard>('/v1/clinical/model-cards', data);
}

export async function updateModelCard(
  id: string,
  data: Partial<ModelCard>
): Promise<ModelCard> {
  return apiClient.put<ModelCard>(`/v1/clinical/model-cards/${id}`, data);
}

export async function publishModelCard(id: string): Promise<ModelCard> {
  return apiClient.post<ModelCard>(`/v1/clinical/model-cards/${id}/publish`);
}

// ─── Auto-fill ──────────────────────────────────────────────
export interface ModelCardAutoFillRequest {
  repo_url: string;
  mlflow_run_id?: string;
  experiment_id?: string;
}

export interface ModelCardAutoFillResult {
  pre_filled: Record<string, any>;
  requires_human_review: string[];
}

export async function autoFillModelCard(
  id: string,
  request: ModelCardAutoFillRequest
): Promise<ModelCardAutoFillResult> {
  return apiClient.post<ModelCardAutoFillResult>(
    `/v1/clinical/model-cards/${id}/auto-fill`,
    request
  );
}

// ─── CHAI compliance scorecard ──────────────────────────────
export interface CHAISection {
  key: string;
  label: string;
  status: 'complete' | 'partial' | 'missing';
  detail?: string | null;
}

export interface CHAICompliance {
  card_id: string;
  score: number;
  total: number;
  percent: number;
  sections: CHAISection[];
  publishable: boolean;
  blockers: string[];
}

export async function getCHAICompliance(id: string): Promise<CHAICompliance> {
  return apiClient.get<CHAICompliance>(`/v1/clinical/model-cards/${id}/chai-compliance`);
}

// ─── Related governance artifacts ──────────────────────────
export interface RelatedArtifact {
  kind: string;
  id: string;
  title: string;
  status?: string | null;
  severity?: string | null;
  timestamp?: string | null;
}

export interface RelatedArtifacts {
  card_id: string;
  bias_audits: RelatedArtifact[];
  drift_baselines: RelatedArtifact[];
  drift_alerts: RelatedArtifact[];
  adverse_events: RelatedArtifact[];
  risk_scores: RelatedArtifact[];
  transparency_records: RelatedArtifact[];
}

export async function getRelatedArtifacts(id: string): Promise<RelatedArtifacts> {
  return apiClient.get<RelatedArtifacts>(`/v1/clinical/model-cards/${id}/related`);
}

// ─── Export (JSON-LD or Markdown) ──────────────────────────
export async function exportModelCard(
  id: string,
  fmt: 'json-ld' | 'markdown' = 'json-ld'
): Promise<any> {
  return apiClient.get(`/v1/clinical/model-cards/${id}/export`, { fmt });
}

// ============================================================
// Bias Audits
// ============================================================

export async function listBiasAudits(params?: {
  model_card_id?: string;
  status?: string;
  page?: number;
}): Promise<PaginatedResponse<BiasAudit>> {
  const raw = await apiClient.get<BiasAudit[] | PaginatedResponse<BiasAudit>>(
    '/v1/clinical/bias-audits', params,
  );
  return toPaginated<BiasAudit>(raw, params?.page);
}

export async function getBiasAudit(id: string): Promise<BiasAudit> {
  return apiClient.get<BiasAudit>(`/v1/clinical/bias-audits/${id}`);
}

export async function runBiasAudit(id: string): Promise<BiasAudit> {
  return apiClient.post<BiasAudit>(`/v1/clinical/bias-audits/${id}/run`);
}

// ============================================================
// Drift
// ============================================================

export async function listDriftMeasurements(params?: {
  model_card_id?: string;
  status?: string;
}): Promise<PaginatedResponse<DriftMeasurement>> {
  // Backend exposes drift alerts (the queryable list); /measure is the POST trigger.
  const raw = await apiClient.get<DriftMeasurement[] | PaginatedResponse<DriftMeasurement>>(
    '/v1/clinical/drift/alerts', params,
  );
  return toPaginated<DriftMeasurement>(raw);
}

export async function listDriftBaselines(modelCardId: string): Promise<PaginatedResponse<DriftBaseline>> {
  const raw = await apiClient.get<DriftBaseline[] | PaginatedResponse<DriftBaseline>>(
    '/v1/clinical/drift/baselines', { model_card_id: modelCardId },
  );
  return toPaginated<DriftBaseline>(raw);
}

// ============================================================
// HITL Reviews
// ============================================================

export async function listHITLReviews(params?: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<HITLReview>> {
  const raw = await apiClient.get<HITLReview[] | PaginatedResponse<HITLReview>>(
    '/v1/clinical/hitl/reviews', params,
  );
  return toPaginated<HITLReview>(raw, params?.page, params?.page_size);
}

export async function getHITLReview(id: string): Promise<HITLReview> {
  return apiClient.get<HITLReview>(`/v1/clinical/hitl/reviews/${id}`);
}

export async function submitHITLDecision(
  id: string,
  decision: {
    status: 'approved' | 'rejected' | 'modified';
    reviewer_decision: string;
    reviewer_notes?: string;
  }
): Promise<HITLReview> {
  // Backend splits the decision into approve / reject endpoints.
  const action = decision.status === 'rejected' ? 'reject' : 'approve';
  return apiClient.post<HITLReview>(`/v1/clinical/hitl/reviews/${id}/${action}`, decision);
}

// ============================================================
// Shadow AI
// ============================================================

export async function listShadowAIDetections(params?: {
  severity?: string;
  page?: number;
}): Promise<PaginatedResponse<ShadowAIDetection>> {
  const raw = await apiClient.get<ShadowAIDetection[] | PaginatedResponse<ShadowAIDetection>>(
    '/v1/admin/shadow-ai/detections', params,
  );
  return toPaginated<ShadowAIDetection>(raw, params?.page);
}

export async function allowlistShadowAI(id: string): Promise<ShadowAIDetection> {
  // Backend marks a detection as reviewed/allowlisted via /detections/{id}/review.
  return apiClient.post<ShadowAIDetection>(`/v1/admin/shadow-ai/detections/${id}/review`, {
    decision: 'allowlist',
  });
}

// ============================================================
// Scribe Audits
// ============================================================

export async function listScribeAudits(params?: {
  status?: string;
  page?: number;
}): Promise<PaginatedResponse<ScribeAudit>> {
  const raw = await apiClient.get<ScribeAudit[] | PaginatedResponse<ScribeAudit>>(
    '/v1/admin/scribe-audits', params,
  );
  return toPaginated<ScribeAudit>(raw, params?.page);
}

// ============================================================
// Transparency
// ============================================================

export async function listTransparencyRecords(params?: {
  page?: number;
}): Promise<PaginatedResponse<TransparencyRecord>> {
  const raw = await apiClient.get<TransparencyRecord[] | PaginatedResponse<TransparencyRecord>>(
    '/v1/transparency', params,
  );
  return toPaginated<TransparencyRecord>(raw, params?.page);
}

export async function createTransparencyRecord(
  data: Omit<TransparencyRecord, 'id' | 'created_at' | 'version'>
): Promise<TransparencyRecord> {
  return apiClient.post<TransparencyRecord>('/v1/transparency', data);
}

// ============================================================
// Prior Auth
// ============================================================

export async function listPriorAuthRecords(params?: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<PriorAuthRecord>> {
  const raw = await apiClient.get<PriorAuthRecord[] | PaginatedResponse<PriorAuthRecord>>(
    '/v1/finance/prior-auth', params,
  );
  return toPaginated<PriorAuthRecord>(raw, params?.page, params?.page_size);
}

export async function verifyPriorAuthChain(id: string): Promise<{ valid: boolean; message: string }> {
  return apiClient.post<{ valid: boolean; message: string }>('/v1/finance/prior-auth/verify-chain', {
    record_id: id,
  });
}

// ============================================================
// Revenue Cycle
// ============================================================

export async function listRevenueCycleAudits(params?: {
  page?: number;
}): Promise<PaginatedResponse<RevenueCycleAudit>> {
  const raw = await apiClient.get<RevenueCycleAudit[] | PaginatedResponse<RevenueCycleAudit>>(
    '/v1/finance/revenue-cycle', params,
  );
  return toPaginated<RevenueCycleAudit>(raw, params?.page);
}

// ============================================================
// Technical Files
// ============================================================

export async function listTechnicalFiles(params?: {
  lifecycle_stage?: string;
  page?: number;
}): Promise<PaginatedResponse<TechnicalFile>> {
  const raw = await apiClient.get<TechnicalFile[] | PaginatedResponse<TechnicalFile>>(
    '/v1/regulatory/technical-files', params,
  );
  return toPaginated<TechnicalFile>(raw, params?.page);
}

// ============================================================
// Adverse Events
// ============================================================

export async function listAdverseEvents(params?: {
  severity?: string;
  status?: string;
  page?: number;
}): Promise<PaginatedResponse<AdverseEvent>> {
  const raw = await apiClient.get<AdverseEvent[] | PaginatedResponse<AdverseEvent>>(
    '/v1/regulatory/adverse-events', params,
  );
  return toPaginated<AdverseEvent>(raw, params?.page);
}

// ============================================================
// PMS Reports
// ============================================================

export async function listPMSReports(params?: {
  page?: number;
}): Promise<PaginatedResponse<PMSReport>> {
  const raw = await apiClient.get<PMSReport[] | PaginatedResponse<PMSReport>>(
    '/v1/regulatory/pms-reports', params,
  );
  return toPaginated<PMSReport>(raw, params?.page);
}

/**
 * Generate a PSUR draft for the previous calendar year via the canonical
 * `POST /v1/regulatory/pms-reports` endpoint with `auto_generate_summary=true`.
 * (There is no dedicated /generate-psur route — this is a convenience wrapper.)
 */
export async function generatePSUR(): Promise<PMSReport> {
  const now = new Date();
  const year = now.getFullYear();
  // Last completed full year
  const start = `${year - 1}-01-01`;
  const end = `${year}-01-01`;
  return apiClient.post<PMSReport>('/v1/regulatory/pms-reports', {
    report_type: 'psur',
    period_start: start,
    period_end: end,
    auto_generate_summary: true,
  });
}

// ============================================================
// Risk
// ============================================================

export async function getRiskPortfolio(): Promise<RiskPortfolio> {
  return apiClient.get<RiskPortfolio>('/v1/risk/portfolio');
}

export async function getRiskScore(modelId: string): Promise<RiskScore> {
  return apiClient.get<RiskScore>(`/v1/risk/scores/${modelId}/latest`);
}

export async function getRiskHistory(modelId: string): Promise<RiskHistoryEntry[]> {
  return apiClient.get<RiskHistoryEntry[]>(`/v1/risk/history/${modelId}`);
}

export async function getRiskConfiguration(): Promise<RiskConfiguration> {
  return apiClient.get<RiskConfiguration>('/v1/risk/configuration');
}

export async function updateRiskConfiguration(
  data: Partial<RiskConfiguration>
): Promise<RiskConfiguration> {
  return apiClient.put<RiskConfiguration>('/v1/risk/configuration', data);
}

// ============================================================
// Organization
// ============================================================

export async function getOrganization(): Promise<{
  id: string;
  name: string;
  slug: string;
  org_type: string;
  hipaa_baa_signed: boolean;
  hipaa_baa_date?: string;
  is_active: boolean;
}> {
  return apiClient.get('/v1/organizations');
}

export async function updateOrganization(data: {
  name?: string;
  org_type?: string;
}): Promise<unknown> {
  return apiClient.put('/v1/organizations/current', data);
}
