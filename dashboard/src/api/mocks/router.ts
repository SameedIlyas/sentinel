/**
 * URL-pattern mock router for VITE_MOCK_API=true.
 *
 * Each handler matches an HTTP method + URL pattern (with `:param` capture)
 * and returns a JSON shape that satisfies the corresponding TypeScript
 * type. Unknown routes fall through to a generic empty response so the
 * UI degrades gracefully instead of throwing.
 */

import * as F from './fixtures';
import { Agent, Policy, ModelCard, User, UserRole } from '@/types';

type Method = 'get' | 'post' | 'put' | 'delete' | 'patch';

interface RouteCtx {
  params: Record<string, string>;
  query?: Record<string, unknown>;
  body?: unknown;
}

type Handler = (ctx: RouteCtx) => unknown;

interface Route {
  method: Method;
  pattern: RegExp;
  keys: string[];
  handler: Handler;
}

function compile(pattern: string): { regex: RegExp; keys: string[] } {
  const keys: string[] = [];
  const regex = new RegExp(
    '^' +
      pattern.replace(/:([A-Za-z_][A-Za-z0-9_]*)/g, (_, k) => {
        keys.push(k);
        return '([^/]+)';
      }) +
      '/?$',
  );
  return { regex, keys };
}

const routes: Route[] = [];

function add(method: Method, pattern: string, handler: Handler) {
  const { regex, keys } = compile(pattern);
  routes.push({ method, pattern: regex, keys, handler });
}

// ── Helpers ────────────────────────────────────────────────────────
function pageOf<T>(
  items: T[],
  q?: Record<string, unknown>,
  defaultSize = 50,
) {
  const page = Math.max(1, Number(q?.page) || 1);
  const pageSize = Math.max(1, Number(q?.page_size) || defaultSize);
  const start = (page - 1) * pageSize;
  const slice = items.slice(start, start + pageSize);
  return {
    items: slice,
    total: items.length,
    page,
    page_size: pageSize,
    total_pages: Math.max(1, Math.ceil(items.length / pageSize)),
  };
}

// Filter helper: apply equality matches from query params to an array.
function applyFilters<T extends Record<string, any>>(
  items: T[],
  q: Record<string, unknown> | undefined,
  fields: string[],
): T[] {
  if (!q) return items;
  return items.filter((item) =>
    fields.every((f) => {
      const v = q[f];
      if (v === undefined || v === null || v === '') return true;
      return String(item[f]) === String(v);
    }),
  );
}

// ── Auth ───────────────────────────────────────────────────────────
add('post', '/v1/auth/login', () => ({
  access_token: '',
  token_type: 'bearer',
  expires_in: 3600,
  user: F.demoUser,
  csrf_token: 'mock-csrf-token',
}));
add('post', '/v1/auth/logout', () => ({ success: true }));
add('post', '/v1/auth/refresh', () => ({
  access_token: '',
  token_type: 'bearer',
  expires_in: 3600,
  user: F.demoUser,
  csrf_token: 'mock-csrf-token',
}));
add('get', '/v1/auth/validate', () => F.demoUser);

// ── Dashboard ──────────────────────────────────────────────────────
add('get', '/v1/dashboard/metrics', () => F.dashboardMetrics);

// ── Agents ─────────────────────────────────────────────────────────
add('get', '/v1/agents', ({ query }) => {
  const filtered = applyFilters(F.agents, query, ['status']);
  const p = pageOf(filtered, query);
  // AgentListResponse uses `agents` not `items`
  return { agents: p.items, total: p.total, page: p.page, page_size: p.page_size, total_pages: p.total_pages };
});
add('get', '/v1/agents/:id', ({ params }) => F.agents.find((a) => a.id === params.id) ?? F.agents[0]);
add('get', '/v1/agents/:id/metrics', ({ params }) => F.agentMetrics[params.id] ?? F.agentMetrics[F.agents[0].id]);
add('put', '/v1/agents/:id', ({ params, body }) => {
  const existing = F.agents.find((a) => a.id === params.id) ?? F.agents[0];
  return { ...existing, ...(body as Partial<Agent>) };
});

// ── Policies ───────────────────────────────────────────────────────
add('get', '/v1/policies', ({ query }) => {
  const filtered = applyFilters(F.policies, query, ['policy_type', 'enabled']);
  const p = pageOf(filtered, query);
  return { policies: p.items, total: p.total, page: p.page, page_size: p.page_size, total_pages: p.total_pages };
});
add('get', '/v1/policies/:id', ({ params }) => F.policies.find((p) => p.id === params.id) ?? F.policies[0]);
add('post', '/v1/policies', ({ body }) => {
  const data = (body ?? {}) as Partial<Policy>;
  return {
    id: `pol_${Date.now().toString(36)}`,
    rules: [],
    applies_to: [],
    enabled: true,
    created_at: F.ISO_NOW,
    ...data,
  };
});
add('put', '/v1/policies/:id', ({ params, body }) => {
  const existing = F.policies.find((p) => p.id === params.id) ?? F.policies[0];
  return { ...existing, ...((body ?? {}) as Partial<Policy>) };
});
add('delete', '/v1/policies/:id', () => ({ success: true, message: 'deleted' }));

// ── Audit logs ─────────────────────────────────────────────────────
add('get', '/v1/audit/logs', ({ query }) => {
  let logs = F.auditLogs;
  if (query?.filter_agent_id) logs = logs.filter((l) => l.agent_id === query.filter_agent_id);
  if (query?.filter_decision) logs = logs.filter((l) => l.decision === query.filter_decision);
  if (query?.filter_tool_name) logs = logs.filter((l) => l.tool_name === query.filter_tool_name);
  const p = pageOf(logs, query);
  return { logs: p.items, total: p.total, page: p.page, page_size: p.page_size, total_pages: p.total_pages };
});
add('get', '/v1/audit/logs/:id', ({ params }) => F.auditLogs.find((l) => l.id === params.id) ?? F.auditLogs[0]);

// ── Alerts ─────────────────────────────────────────────────────────
add('get', '/v1/alerts', ({ query }) => {
  let list = F.alerts;
  if (query?.severity) list = list.filter((a) => a.severity === query.severity);
  if (query?.acknowledged !== undefined) {
    const ack = String(query.acknowledged) === 'true';
    list = list.filter((a) => a.acknowledged === ack);
  }
  const p = pageOf(list, query);
  return { alerts: p.items, total: p.total, page: p.page, page_size: p.page_size, total_pages: p.total_pages };
});
add('get', '/v1/alerts/:id', ({ params }) => F.alerts.find((a) => a.id === params.id) ?? F.alerts[0]);
add('post', '/v1/alerts/:id/acknowledge', ({ params, body }) => {
  const a = F.alerts.find((x) => x.id === params.id) ?? F.alerts[0];
  const b = (body ?? {}) as { acknowledged_by?: string };
  return { ...a, acknowledged: true, acknowledged_by: b.acknowledged_by ?? 'demo.admin', acknowledged_at: F.ISO_NOW };
});
add('get', '/v1/alerts/rules/list', () => F.alertRules);
add('post', '/v1/alerts/configure', ({ body }) => ({
  message: 'Demo mode — configuration accepted but not persisted.',
  global_webhook_configured: !!(body as any)?.global_slack_webhook,
  rules_created: ((body as any)?.alert_rules ?? []).length,
  rules: F.alertRules,
}));
add('post', '/v1/alerts/test', () => ({ success: true, message: 'Demo mode: webhook test simulated successfully.' }));

// ── Users ──────────────────────────────────────────────────────────
add('get', '/v1/users', ({ query }) => {
  let list = F.users;
  if (query?.role_filter) list = list.filter((u) => u.role === query.role_filter);
  if (query?.is_active !== undefined) {
    const active = String(query.is_active) === 'true';
    list = list.filter((u) => u.is_active === active);
  }
  const p = pageOf(list, query);
  return { users: p.items, total: p.total, page: p.page, page_size: p.page_size, total_pages: p.total_pages };
});
add('get', '/v1/users/:id', ({ params }) => F.users.find((u) => u.id === params.id) ?? F.users[0]);
add('post', '/v1/users', ({ body }) => {
  const data = (body ?? {}) as Partial<User>;
  return {
    id: `usr_${Date.now().toString(36)}`,
    role: UserRole.VIEWER,
    is_active: true,
    organization_id: 'demo-org-001',
    tier: 'enterprise' as const,
    created_at: F.ISO_NOW,
    ...data,
  };
});
add('put', '/v1/users/:id', ({ params, body }) => {
  const u = F.users.find((x) => x.id === params.id) ?? F.users[0];
  return { ...u, ...((body ?? {}) as Partial<User>) };
});
add('delete', '/v1/users/:id', () => ({ success: true }));
add('post', '/v1/users/:id/change-password', ({ params }) => F.users.find((u) => u.id === params.id) ?? F.users[0]);
add('post', '/v1/users/assign-role', ({ body }) => {
  const b = (body ?? {}) as { user_id?: string; role?: string };
  const u = F.users.find((x) => x.id === b.user_id) ?? F.users[0];
  return { ...u, role: (b.role as UserRole) ?? u.role };
});

// ── Clinical: model cards ──────────────────────────────────────────
add('get', '/v1/clinical/model-cards', ({ query }) => {
  const filtered = applyFilters(F.modelCards, query, ['lifecycle_stage']);
  return pageOf(filtered, query);
});
add('get', '/v1/clinical/model-cards/:id', ({ params }) => F.modelCards.find((m) => m.id === params.id) ?? F.modelCards[0]);
add('post', '/v1/clinical/model-cards', ({ body }) => {
  const data = (body ?? {}) as Partial<ModelCard>;
  return {
    id: `mc_${Date.now().toString(36)}`,
    lifecycle_stage: 'draft' as const,
    created_at: F.ISO_NOW,
    updated_at: F.ISO_NOW,
    ...data,
  };
});
add('put', '/v1/clinical/model-cards/:id', ({ params, body }) => {
  const mc = F.modelCards.find((m) => m.id === params.id) ?? F.modelCards[0];
  return { ...mc, ...((body ?? {}) as Partial<ModelCard>), updated_at: F.ISO_NOW };
});
add('post', '/v1/clinical/model-cards/:id/publish', ({ params }) => {
  const mc = F.modelCards.find((m) => m.id === params.id) ?? F.modelCards[0];
  return { ...mc, lifecycle_stage: 'published' as const, updated_at: F.ISO_NOW };
});
add('post', '/v1/clinical/model-cards/:id/auto-fill', () => ({
  pre_filled: {
    training_data_source: 'Auto-extracted from repository README.',
    performance_summary: 'Auto-extracted from MLflow run metrics.',
  },
  requires_human_review: ['bias_summary', 'contraindications', 'clinical_indications'],
}));
add('get', '/v1/clinical/model-cards/:id/chai-compliance', ({ params }) => F.chaiCompliance(params.id));
add('get', '/v1/clinical/model-cards/:id/related', ({ params }) => F.relatedArtifacts(params.id));
add('get', '/v1/clinical/model-cards/:id/export', () => ({ format: 'json-ld', exported_at: F.ISO_NOW }));

// ── Clinical: bias audits ──────────────────────────────────────────
add('get', '/v1/clinical/bias-audits', ({ query }) => {
  const filtered = applyFilters(F.biasAudits, query, ['status', 'model_card_id']);
  return pageOf(filtered, query);
});
add('get', '/v1/clinical/bias-audits/:id', ({ params }) => F.biasAudits.find((b) => b.id === params.id) ?? F.biasAudits[0]);
add('post', '/v1/clinical/bias-audits/:id/run', ({ params }) => {
  const ba = F.biasAudits.find((b) => b.id === params.id) ?? F.biasAudits[0];
  return { ...ba, status: 'running' as const };
});

// ── Clinical: drift ────────────────────────────────────────────────
add('get', '/v1/clinical/drift/alerts', ({ query }) => {
  const filtered = applyFilters(F.driftMeasurements, query, ['status']);
  return pageOf(filtered, query);
});
add('get', '/v1/clinical/drift/baselines', ({ query }) => {
  let list = F.driftBaselines;
  if (query?.model_card_id) list = list.filter((d) => d.model_card_id === query.model_card_id);
  return pageOf(list, query);
});

// ── Clinical: HITL reviews ─────────────────────────────────────────
add('get', '/v1/clinical/hitl/reviews', ({ query }) => {
  const filtered = applyFilters(F.hitlReviews, query, ['status']);
  return pageOf(filtered, query);
});
add('get', '/v1/clinical/hitl/reviews/:id', ({ params }) => F.hitlReviews.find((h) => h.id === params.id) ?? F.hitlReviews[0]);
add('post', '/v1/clinical/hitl/reviews/:id/approve', ({ params, body }) => {
  const h = F.hitlReviews.find((x) => x.id === params.id) ?? F.hitlReviews[0];
  return { ...h, status: 'approved' as const, ...((body ?? {}) as object), reviewed_at: F.ISO_NOW };
});
add('post', '/v1/clinical/hitl/reviews/:id/reject', ({ params, body }) => {
  const h = F.hitlReviews.find((x) => x.id === params.id) ?? F.hitlReviews[0];
  return { ...h, status: 'rejected' as const, ...((body ?? {}) as object), reviewed_at: F.ISO_NOW };
});

// ── Admin: shadow AI ───────────────────────────────────────────────
add('get', '/v1/admin/shadow-ai/detections', ({ query }) => {
  const filtered = applyFilters(F.shadowAIDetections, query, ['severity']);
  return pageOf(filtered, query);
});
add('post', '/v1/admin/shadow-ai/detections/:id/review', ({ params, body }) => {
  const d = F.shadowAIDetections.find((x) => x.id === params.id) ?? F.shadowAIDetections[0];
  const decision = (body as any)?.decision;
  return { ...d, allowlisted: decision === 'allowlist' };
});

// ── Admin: scribe audits ───────────────────────────────────────────
add('get', '/v1/admin/scribe-audits', ({ query }) => {
  const filtered = applyFilters(F.scribeAudits, query, ['status']);
  return pageOf(filtered, query);
});

// ── Admin: transparency ────────────────────────────────────────────
add('get', '/v1/transparency', ({ query }) => pageOf(F.transparencyRecords, query));
add('post', '/v1/transparency', ({ body }) => {
  const data = (body ?? {}) as any;
  return {
    id: `tr_${Date.now().toString(36)}`,
    version: 1,
    created_at: F.ISO_NOW,
    ...data,
  };
});

// ── Finance: prior auth ────────────────────────────────────────────
add('get', '/v1/finance/prior-auth', ({ query }) => pageOf(F.priorAuthRecords, query));
add('post', '/v1/finance/prior-auth/verify-chain', () => ({
  valid: true,
  message: 'Chain integrity verified across 35 records. No tail-deletion or tampering detected.',
}));

// ── Finance: revenue cycle ─────────────────────────────────────────
add('get', '/v1/finance/revenue-cycle', ({ query }) => pageOf(F.revenueCycleAudits, query));

// ── Regulatory ─────────────────────────────────────────────────────
add('get', '/v1/regulatory/technical-files', ({ query }) => {
  const filtered = applyFilters(F.technicalFiles, query, ['lifecycle_stage']);
  return pageOf(filtered, query);
});
add('get', '/v1/regulatory/adverse-events', ({ query }) => {
  const filtered = applyFilters(F.adverseEvents, query, ['severity', 'status']);
  return pageOf(filtered, query);
});
add('get', '/v1/regulatory/pms-reports', ({ query }) => pageOf(F.pmsReports, query));
add('post', '/v1/regulatory/pms-reports', ({ body }) => {
  const data = (body ?? {}) as any;
  return {
    id: `pms_${Date.now().toString(36)}`,
    status: 'draft' as const,
    created_by: 'demo.admin',
    created_at: F.ISO_NOW,
    ...data,
  };
});

// ── Risk ───────────────────────────────────────────────────────────
add('get', '/v1/risk/portfolio', () => F.riskPortfolio);
add('get', '/v1/risk/scores/:modelId/latest', ({ params }) =>
  F.riskScores[params.modelId] ?? F.riskScores[F.modelCards[0].id],
);
add('get', '/v1/risk/history/:modelId', ({ params }) =>
  F.riskHistory[params.modelId] ?? F.riskHistory[F.modelCards[0].id],
);
add('get', '/v1/risk/configuration', () => F.riskConfiguration);
add('put', '/v1/risk/configuration', ({ body }) => ({
  ...F.riskConfiguration,
  ...((body ?? {}) as Partial<typeof F.riskConfiguration>),
}));

// ── Organization ───────────────────────────────────────────────────
add('get', '/v1/organizations', () => F.organization);
add('put', '/v1/organizations/current', ({ body }) => ({ ...F.organization, ...((body ?? {}) as any) }));

// ── Dispatcher ─────────────────────────────────────────────────────
export function dispatchMock<T = unknown>(
  method: Method,
  url: string,
  query?: Record<string, unknown>,
  body?: unknown,
): T {
  // Strip query string if accidentally included
  const path = url.split('?')[0];
  for (const route of routes) {
    if (route.method !== method) continue;
    const match = route.pattern.exec(path);
    if (!match) continue;
    const params: Record<string, string> = {};
    route.keys.forEach((k, i) => {
      params[k] = decodeURIComponent(match[i + 1] ?? '');
    });
    return route.handler({ params, query, body }) as T;
  }
  // Fallback: log once-per-route in dev so we know what to add.
  if (typeof console !== 'undefined') {
    // eslint-disable-next-line no-console
    console.warn(`[mock-api] no handler for ${method.toUpperCase()} ${path} — returning empty payload`);
  }
  // Return a permissive empty shape that works for most list/detail callers.
  return {
    items: [],
    total: 0,
    page: 1,
    page_size: 50,
    total_pages: 1,
  } as unknown as T;
}

export const MOCK_DELAY_MS = 80;

export function withDelay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_DELAY_MS));
}
