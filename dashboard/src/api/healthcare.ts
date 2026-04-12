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

// ============================================================
// Model Cards
// ============================================================

export async function listModelCards(params?: {
  lifecycle_stage?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<ModelCard>> {
  return apiClient.get<PaginatedResponse<ModelCard>>('/v2/clinical/model-cards', params);
}

export async function getModelCard(id: string): Promise<ModelCard> {
  return apiClient.get<ModelCard>(`/v2/clinical/model-cards/${id}`);
}

export async function createModelCard(
  data: Omit<ModelCard, 'id' | 'created_at' | 'updated_at' | 'created_by'>
): Promise<ModelCard> {
  return apiClient.post<ModelCard>('/v2/clinical/model-cards', data);
}

export async function updateModelCard(
  id: string,
  data: Partial<ModelCard>
): Promise<ModelCard> {
  return apiClient.put<ModelCard>(`/v2/clinical/model-cards/${id}`, data);
}

export async function publishModelCard(id: string): Promise<ModelCard> {
  return apiClient.post<ModelCard>(`/v2/clinical/model-cards/${id}/publish`);
}

// ============================================================
// Bias Audits
// ============================================================

export async function listBiasAudits(params?: {
  model_card_id?: string;
  status?: string;
  page?: number;
}): Promise<PaginatedResponse<BiasAudit>> {
  return apiClient.get<PaginatedResponse<BiasAudit>>('/v2/clinical/bias-audits', params);
}

export async function getBiasAudit(id: string): Promise<BiasAudit> {
  return apiClient.get<BiasAudit>(`/v2/clinical/bias-audits/${id}`);
}

export async function runBiasAudit(id: string): Promise<BiasAudit> {
  return apiClient.post<BiasAudit>(`/v2/clinical/bias-audits/${id}/run`);
}

// ============================================================
// Drift
// ============================================================

export async function listDriftMeasurements(params?: {
  model_card_id?: string;
  status?: string;
}): Promise<PaginatedResponse<DriftMeasurement>> {
  return apiClient.get<PaginatedResponse<DriftMeasurement>>('/v2/clinical/drift/measurements', params);
}

export async function listDriftBaselines(modelCardId: string): Promise<PaginatedResponse<DriftBaseline>> {
  return apiClient.get<PaginatedResponse<DriftBaseline>>('/v2/clinical/drift/baselines', {
    model_card_id: modelCardId,
  });
}

// ============================================================
// HITL Reviews
// ============================================================

export async function listHITLReviews(params?: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<HITLReview>> {
  return apiClient.get<PaginatedResponse<HITLReview>>('/v2/clinical/hitl', params);
}

export async function getHITLReview(id: string): Promise<HITLReview> {
  return apiClient.get<HITLReview>(`/v2/clinical/hitl/${id}`);
}

export async function submitHITLDecision(
  id: string,
  decision: {
    status: 'approved' | 'rejected' | 'modified';
    reviewer_decision: string;
    reviewer_notes?: string;
  }
): Promise<HITLReview> {
  return apiClient.post<HITLReview>(`/v2/clinical/hitl/${id}/decision`, decision);
}

// ============================================================
// Shadow AI
// ============================================================

export async function listShadowAIDetections(params?: {
  severity?: string;
  page?: number;
}): Promise<PaginatedResponse<ShadowAIDetection>> {
  return apiClient.get<PaginatedResponse<ShadowAIDetection>>('/v2/admin/shadow-ai', params);
}

export async function allowlistShadowAI(id: string): Promise<ShadowAIDetection> {
  return apiClient.post<ShadowAIDetection>(`/v2/admin/shadow-ai/${id}/allowlist`);
}

// ============================================================
// Scribe Audits
// ============================================================

export async function listScribeAudits(params?: {
  status?: string;
  page?: number;
}): Promise<PaginatedResponse<ScribeAudit>> {
  return apiClient.get<PaginatedResponse<ScribeAudit>>('/v2/admin/scribe-audits', params);
}

// ============================================================
// Transparency
// ============================================================

export async function listTransparencyRecords(params?: {
  page?: number;
}): Promise<PaginatedResponse<TransparencyRecord>> {
  return apiClient.get<PaginatedResponse<TransparencyRecord>>('/v2/transparency', params);
}

export async function createTransparencyRecord(
  data: Omit<TransparencyRecord, 'id' | 'created_at' | 'version'>
): Promise<TransparencyRecord> {
  return apiClient.post<TransparencyRecord>('/v2/transparency', data);
}

// ============================================================
// Prior Auth
// ============================================================

export async function listPriorAuthRecords(params?: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<PriorAuthRecord>> {
  return apiClient.get<PaginatedResponse<PriorAuthRecord>>('/v2/finance/prior-auth', params);
}

export async function verifyPriorAuthChain(id: string): Promise<{ valid: boolean; message: string }> {
  return apiClient.post<{ valid: boolean; message: string }>(`/v2/finance/prior-auth/${id}/verify`);
}

// ============================================================
// Revenue Cycle
// ============================================================

export async function listRevenueCycleAudits(params?: {
  page?: number;
}): Promise<PaginatedResponse<RevenueCycleAudit>> {
  return apiClient.get<PaginatedResponse<RevenueCycleAudit>>('/v2/finance/revenue-cycle', params);
}

// ============================================================
// Technical Files
// ============================================================

export async function listTechnicalFiles(params?: {
  lifecycle_stage?: string;
  page?: number;
}): Promise<PaginatedResponse<TechnicalFile>> {
  return apiClient.get<PaginatedResponse<TechnicalFile>>('/v2/regulatory/technical-files', params);
}

// ============================================================
// Adverse Events
// ============================================================

export async function listAdverseEvents(params?: {
  severity?: string;
  status?: string;
  page?: number;
}): Promise<PaginatedResponse<AdverseEvent>> {
  return apiClient.get<PaginatedResponse<AdverseEvent>>('/v2/regulatory/adverse-events', params);
}

// ============================================================
// PMS Reports
// ============================================================

export async function listPMSReports(params?: {
  page?: number;
}): Promise<PaginatedResponse<PMSReport>> {
  return apiClient.get<PaginatedResponse<PMSReport>>('/v2/regulatory/pms-reports', params);
}

export async function generatePSUR(): Promise<PMSReport> {
  return apiClient.post<PMSReport>('/v2/regulatory/pms-reports/generate-psur');
}

// ============================================================
// Risk
// ============================================================

export async function getRiskPortfolio(): Promise<RiskPortfolio> {
  return apiClient.get<RiskPortfolio>('/v2/risk/portfolio');
}

export async function getRiskScore(modelId: string): Promise<RiskScore> {
  return apiClient.get<RiskScore>(`/v2/risk/score/${modelId}`);
}

export async function getRiskHistory(modelId: string): Promise<RiskHistoryEntry[]> {
  return apiClient.get<RiskHistoryEntry[]>(`/v2/risk/history/${modelId}`);
}

export async function getRiskConfiguration(): Promise<RiskConfiguration> {
  return apiClient.get<RiskConfiguration>('/v2/risk/configuration');
}

export async function updateRiskConfiguration(
  data: Partial<RiskConfiguration>
): Promise<RiskConfiguration> {
  return apiClient.put<RiskConfiguration>('/v2/risk/configuration', data);
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
  return apiClient.get('/v2/organizations/current');
}

export async function updateOrganization(data: {
  name?: string;
  org_type?: string;
}): Promise<unknown> {
  return apiClient.put('/v2/organizations/current', data);
}
