/**
 * Sentinel first-run walkthrough — step content.
 *
 * Steps are grouped roughly by the sidebar navigation order. Each one
 * teaches a single concept and asks the user to either click "Next" or
 * interact with the spotlit element to advance. Everything below is plain
 * data — the engine in `WalkthroughProvider` and `WalkthroughOverlay`
 * handles routing, scrolling, measurement, and rendering.
 */
import type { WalkthroughStep } from './types';

export const TOUR_VERSION = 'v1';

export const STEPS: WalkthroughStep[] = [
  // ── 1. Welcome ─────────────────────────────────────────────────────────
  {
    id: 'welcome',
    title: 'Welcome to Sentinel',
    body:
      "Sentinel is your AI governance control tower. In ~3 minutes I'll walk you through every page and what it's for. " +
      'You can skip at any time — and replay the tour later from the user menu.',
    target: null,
    placement: 'center',
    accent: 'primary',
    actionHint: 'Click "Next" to start',
  },

  // ── 2. Sidebar — overview ──────────────────────────────────────────────
  {
    id: 'sidebar',
    title: 'The sidebar',
    body:
      'Every Sentinel feature lives behind one of these sections. They group naturally: Core (your agents and policies), ' +
      'Clinical Governance (model cards, bias, drift, HITL), Admin Governance (shadow AI, scribes, transparency), ' +
      'Finance, Regulatory, and Risk.',
    target: '[data-walkthrough="sidebar"]',
    placement: 'right',
    accent: 'primary',
  },

  // ── 3. Dashboard ───────────────────────────────────────────────────────
  {
    id: 'dashboard',
    title: 'Dashboard — your control tower',
    body:
      "Live snapshot of every governed agent: what's running now, how many policy violations fired in the last 24 hours, " +
      'and the open-alerts queue. Real-time via WebSocket — no manual refresh.',
    target: '[data-walkthrough="nav-Dashboard"]',
    path: '/',
    placement: 'right',
  },

  // ── 4. Agents ──────────────────────────────────────────────────────────
  {
    id: 'agents',
    title: 'Agents',
    body:
      'Every AI agent that has ever called the Sentinel SDK. Auto-registered on first call — no manual onboarding. ' +
      'You can drill into any agent to see its tool history, policy hits, and PHI access.',
    target: '[data-walkthrough="nav-Agents"]',
    path: '/agents',
    placement: 'right',
    actionHint: 'Click an agent in the list to see its detail view',
  },

  // ── 5. Policies ────────────────────────────────────────────────────────
  {
    id: 'policies',
    title: 'Policies',
    body:
      'The rule engine. A policy says: "for tool X with arguments Y, do Z (allow / block / require_approval / mask)." ' +
      'Sentinel evaluates every tool call against these in real time. ' +
      'Tier 2: when a policy returns require_approval, a HITL review row is created automatically.',
    target: '[data-walkthrough="nav-Policies"]',
    path: '/policies',
    placement: 'right',
  },

  // ── 6. Audit Logs ──────────────────────────────────────────────────────
  {
    id: 'audit',
    title: 'Audit logs',
    body:
      'Every decision Sentinel ever made, append-only and PHI-redacted. Use this for HIPAA "minimum necessary" reviews ' +
      'and incident forensics. The data here also feeds the daily Risk recompute job.',
    target: '[data-walkthrough="nav-Audit Logs"]',
    path: '/audit',
    placement: 'right',
  },

  // ── 7. Alerts ──────────────────────────────────────────────────────────
  {
    id: 'alerts',
    title: 'Alerts',
    body:
      "Sentinel raises alerts when something deserves human attention: blocked actions, new agents that haven't been " +
      'reviewed, PHI-protection violations. Alerts deduplicate within a 5-minute window so retries don\'t flood the queue.',
    target: '[data-walkthrough="nav-Alerts"]',
    path: '/alerts',
    placement: 'right',
  },

  // ── 8. Clinical Governance — Model Cards ───────────────────────────────
  {
    id: 'model-cards',
    title: 'Model Cards (CHAI v2.0)',
    body:
      'The official record for every clinical AI model: intended use, training data, fairness, lineage. ' +
      'Tier 2 publish gate: a model card cannot go live without (1) pinned artifact lineage, ' +
      '(2) a complete bias audit < 90 days old. On publish, a Transparency draft is auto-generated.',
    target: '[data-walkthrough="nav-Model Cards"]',
    path: '/clinical/model-cards',
    placement: 'right',
  },

  // ── 9. Drift Monitor ───────────────────────────────────────────────────
  {
    id: 'drift',
    title: 'Drift Monitor',
    body:
      "Population drift breaks calibrated models silently. The drift monitor tracks PSI and KS-test p-values per feature " +
      'against a baseline. Tier 2: inference servers running the Sentinel SDK auto-stream their predictions here every minute, ' +
      'and a 6-hour recompute job creates DriftAlerts when PSI > 0.2.',
    target: '[data-walkthrough="nav-Drift Monitor"]',
    path: '/clinical/drift',
    placement: 'right',
  },

  // ── 10. HITL Queue ─────────────────────────────────────────────────────
  {
    id: 'hitl',
    title: 'Human-In-The-Loop queue',
    body:
      'Where humans review AI decisions that need their judgement. SLA-tracked, hash-chain audited, escalatable. ' +
      'Tier 2 wired the auto-create flow: any policy returning require_approval, any drift alert, any failing bias audit ' +
      'now lands here automatically with the right priority and SLA.',
    target: '[data-walkthrough="nav-HITL Queue"]',
    path: '/clinical/hitl',
    placement: 'right',
  },

  // ── 11. Admin Governance — Shadow AI ───────────────────────────────────
  {
    id: 'shadow-ai',
    title: 'Shadow AI Discovery',
    body:
      "Catches employees using AI tools outside the governance perimeter — pasting PHI into ChatGPT, calling api.openai.com " +
      'from an unapproved department, etc. Tier 3 added the ingest pipeline: point Cloudflare Logpush, Zscaler, or VPC Flow Logs ' +
      "at /v1/admin/shadow-ai/ingest and detections appear here in real time. We classify against a curated provider host list.",
    target: '[data-walkthrough="nav-Shadow AI"]',
    path: '/admin/shadow-ai',
    placement: 'right',
    accent: 'warning',
  },

  // ── 12. Scribe Audits ──────────────────────────────────────────────────
  {
    id: 'scribe-audits',
    title: 'Ambient-scribe Audits',
    body:
      "AI scribes (Abridge, Nabla, Suki, DeepScribe) generate notes from doctor-patient encounters. They sometimes hallucinate. " +
      'This page audits each note against the encounter transcript: completeness, attribution, hallucination detection. ' +
      'Tier 3 added the LLM fact-checker and vendor webhook adapters.',
    target: '[data-walkthrough="nav-Scribe Audits"]',
    path: '/admin/scribe-audits',
    placement: 'right',
    accent: 'warning',
  },

  // ── 13. Transparency Portal ────────────────────────────────────────────
  {
    id: 'transparency',
    title: 'Transparency Portal',
    body:
      'The patient-facing record of every AI used in their care: plain-language summary, intended use, limitations. ' +
      'Required by ONC HTI-1 and the 21st Century Cures Act. Tier 2 auto-generates a draft from the model card on publish; ' +
      'compliance officer reviews and ships.',
    target: '[data-walkthrough="nav-Transparency"]',
    path: '/transparency',
    placement: 'right',
  },

  // ── 14. Finance ────────────────────────────────────────────────────────
  {
    id: 'finance',
    title: 'Finance — prior auth + revenue cycle',
    body:
      'Audit-trailed records of every AI-driven financial action: prior authorisations, claims edits, denials. Built for ' +
      'CMS False Claims Act compliance and post-audit defensibility. Hash-chain integrity per record.',
    target: '[data-walkthrough="nav-Prior Auth"]',
    path: '/finance/prior-auth',
    placement: 'right',
  },

  // ── 15. Regulatory ─────────────────────────────────────────────────────
  {
    id: 'regulatory',
    title: 'Regulatory',
    body:
      'Three artifacts auditors actually demand: Technical Files (FDA 510(k) / EU MDR), Adverse Events (MDR-eligible), and ' +
      'Periodic Safety Updates (PSUR). Tier 2 ships scheduled quarterly + annual auto-generation; Tier 4 will add Epic ingestion.',
    target: '[data-walkthrough="nav-Technical Files"]',
    path: '/regulatory/technical-files',
    placement: 'right',
  },

  // ── 16. Risk Portfolio ─────────────────────────────────────────────────
  {
    id: 'risk',
    title: 'Risk Portfolio',
    body:
      'Live risk score per published model — severity × exposure + regulatory penalty. ' +
      'Tier 2 daily recompute pulls real signals: latest adverse events, drift magnitude, bias-audit disparity, ' +
      'audit-log volume. "Which model is currently most risky?" becomes one query, not a quarterly review.',
    target: '[data-walkthrough="nav-Risk Portfolio"]',
    path: '/risk/portfolio',
    placement: 'right',
    accent: 'warning',
  },

  // ── 17. Settings ───────────────────────────────────────────────────────
  {
    id: 'settings',
    title: 'Settings',
    body:
      'Org-level configuration: branding, risk thresholds, HIPAA encryption keys, archive backends. Most teams set this once ' +
      'and forget. Per-org thresholds let you say "anything > 75 is critical, alert the CMIO" without changing the formula.',
    target: '[data-walkthrough="nav-Organization"]',
    path: '/settings/organization',
    placement: 'right',
  },

  // ── 18. Theme toggle ───────────────────────────────────────────────────
  {
    id: 'theme',
    title: 'Light / dark theme',
    body:
      'Toggle anytime. Sentinel respects your preference across sessions. Both themes are designed for the same ' +
      'governance workflows — no functional difference.',
    target: '[data-walkthrough="theme-toggle"]',
    placement: 'bottom',
  },

  // ── 19. User menu ──────────────────────────────────────────────────────
  {
    id: 'user-menu',
    title: 'Your account',
    body:
      'Sign out, or restart this walkthrough anytime via "Restart tour". You can also see your role here — Sentinel ' +
      'enforces role-based access throughout the app.',
    target: '[data-walkthrough="user-menu"]',
    placement: 'bottom',
  },

  // ── 20. Wrap-up ────────────────────────────────────────────────────────
  {
    id: 'wrap-up',
    title: "You're set",
    body:
      "That's the whole governance surface. To start using Sentinel: install the SDK, point it at your existing AI agents, " +
      "and watch the dashboards populate. If you ever want to replay this tour, look for \"Restart tour\" in the user menu " +
      "(top right). Good luck — your auditors will thank you.",
    target: null,
    placement: 'center',
    accent: 'success',
    actionHint: 'Click "Finish" to close',
  },
];
