import React, { useMemo, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import {
  ThemeProvider, createTheme, CssBaseline, alpha, CircularProgress, Box,
  type PaletteMode,
} from '@mui/material';
import { ThemeModeProvider, useThemeMode } from '@/contexts/ThemeContext';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import Login from '@/components/auth/Login';
import AppLayout from '@/components/layout/AppLayout';
import { UserRole, CLINIC_TIERS } from '@/types';
import { WalkthroughProvider } from '@/walkthrough';
import { I18nProvider } from '@/i18n';

// ── Eager-loaded core pages (above the fold, small bundle impact) ──
import Dashboard from '@/pages/Dashboard';

// ── Lazy-loaded pages ──
// Core
const AgentList          = React.lazy(() => import('@/pages/AgentList'));
const AgentDetail        = React.lazy(() => import('@/pages/AgentDetail'));
const PolicyList         = React.lazy(() => import('@/pages/PolicyList'));
const PolicyEditor       = React.lazy(() => import('@/pages/PolicyEditor'));
const AuditLogs          = React.lazy(() => import('@/pages/AuditLogs'));
const Alerts             = React.lazy(() => import('@/pages/Alerts'));
const Users              = React.lazy(() => import('@/pages/Users'));

// Clinical Governance
const ModelCardList      = React.lazy(() => import('@/pages/clinical/ModelCardList'));
const ModelCardEditor    = React.lazy(() => import('@/pages/clinical/ModelCardEditor'));
const BiasAuditList      = React.lazy(() => import('@/pages/clinical/BiasAuditList'));
const BiasAuditDetail    = React.lazy(() => import('@/pages/clinical/BiasAuditDetail'));
const DriftMonitor       = React.lazy(() => import('@/pages/clinical/DriftMonitor'));
const HITLQueue          = React.lazy(() => import('@/pages/clinical/HITLQueue'));
const HITLReviewDetail   = React.lazy(() => import('@/pages/clinical/HITLReviewDetail'));

// Admin Governance
const ShadowAIDiscovery  = React.lazy(() => import('@/pages/admin/ShadowAIDiscovery'));
const ScribeAuditList    = React.lazy(() => import('@/pages/admin/ScribeAuditList'));
const TransparencyPortal = React.lazy(() => import('@/pages/admin/TransparencyPortal'));

// Financial
const PriorAuthTrail     = React.lazy(() => import('@/pages/finance/PriorAuthTrail'));
const RevenueCycleAudit  = React.lazy(() => import('@/pages/finance/RevenueCycleAudit'));

// Regulatory
const TechnicalFiles          = React.lazy(() => import('@/pages/regulatory/TechnicalFiles'));
const AdverseEvents           = React.lazy(() => import('@/pages/regulatory/AdverseEvents'));
const PostMarketSurveillance  = React.lazy(() => import('@/pages/regulatory/PostMarketSurveillance'));

// Risk
const RiskPortfolio      = React.lazy(() => import('@/pages/risk/RiskPortfolio'));
const RiskScoreDetail    = React.lazy(() => import('@/pages/risk/RiskScoreDetail'));

// Settings
const OrganizationSettings = React.lazy(() => import('@/pages/settings/OrganizationSettings'));
const RiskConfiguration    = React.lazy(() => import('@/pages/settings/RiskConfiguration'));
const HIPAAConfiguration   = React.lazy(() => import('@/pages/settings/HIPAAConfiguration'));

// Clinic-tier pages
const ClinicDashboard       = React.lazy(() => import('@/pages/clinic/ClinicDashboard'));
const ClinicToolList        = React.lazy(() => import('@/pages/clinic/ToolList'));
const ClinicToolEditor      = React.lazy(() => import('@/pages/clinic/ToolEditor'));
const ClinicPolicyLibrary   = React.lazy(() => import('@/pages/clinic/PolicyLibrary'));
const ClinicAlertCenter     = React.lazy(() => import('@/pages/clinic/AlertCenter'));
const ClinicShadowAi        = React.lazy(() => import('@/pages/clinic/ShadowAiWatcher'));
const ClinicReports         = React.lazy(() => import('@/pages/clinic/Reports'));
const ClinicOnboarding      = React.lazy(() => import('@/pages/clinic/OnboardingWizard'));
const ClinicPracticeSet     = React.lazy(() => import('@/pages/clinic/settings/Practice'));
const ClinicComplianceSet   = React.lazy(() => import('@/pages/clinic/settings/Compliance'));
const ClinicBillingSet      = React.lazy(() => import('@/pages/clinic/settings/Billing'));

// ── Design tokens ──────────────────────────────────────────────────
const ACCENT = { main: '#635bff', light: '#7a73ff', dark: '#5046e5' };

function buildTheme(mode: PaletteMode) {
  const dark = mode === 'dark';

  const bg          = dark ? { default: '#0a0a0c', paper: '#111114' } : { default: '#f6f8fa', paper: '#ffffff' };
  const text        = dark ? { primary: '#f0f2f5', secondary: '#8b8fa3' } : { primary: '#1a1f36', secondary: '#697386' };
  const border      = dark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.08)';
  const hoverBg     = dark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.03)';
  const surfaceHover= dark ? 'rgba(255,255,255,0.05)'  : 'rgba(0,0,0,0.015)';
  const scrollThumb = dark ? '#2a2a2e' : '#c8c8cc';
  const scrollHover = dark ? '#3f3f44' : '#a0a0a6';

  return createTheme({
    palette: {
      mode,
      primary: ACCENT,
      secondary: { main: '#a78bfa', light: '#c4b5fd', dark: '#7c3aed' },
      success:   { main: '#0ea371', light: '#3ecf8e', dark: '#067a55' },
      warning:   { main: '#e87f17', light: '#f5a623', dark: '#c26a0a' },
      error:     { main: '#df1b41', light: '#f04662', dark: '#b31535' },
      info:      { main: '#3b82f6', light: '#60a5fa', dark: '#2563eb' },
      background: bg,
      text,
      divider: border,
    },
    typography: {
      fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      h1: { fontWeight: 700, letterSpacing: '-0.025em', fontSize: '2rem' },
      h2: { fontWeight: 700, letterSpacing: '-0.02em',  fontSize: '1.5rem' },
      h3: { fontWeight: 600, letterSpacing: '-0.02em',  fontSize: '1.25rem' },
      h4: { fontWeight: 600, letterSpacing: '-0.015em', fontSize: '1.125rem' },
      h5: { fontWeight: 600, letterSpacing: '-0.01em',  fontSize: '1rem' },
      h6: { fontWeight: 600, fontSize: '0.875rem' },
      subtitle1: { fontWeight: 500, fontSize: '0.9375rem', color: text.secondary },
      subtitle2: { fontWeight: 500, fontSize: '0.8125rem', color: text.secondary },
      body1:     { fontSize: '0.875rem',   lineHeight: 1.65, color: text.primary },
      body2:     { fontSize: '0.8125rem',  lineHeight: 1.55, color: text.secondary },
      caption:   { fontSize: '0.6875rem',  letterSpacing: '0.02em', color: text.secondary },
      button:    { fontWeight: 600, fontSize: '0.8125rem', letterSpacing: '0.01em' },
    },
    shape: { borderRadius: 8 },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          html: { overflowX: 'hidden' },
          body: { backgroundColor: bg.default, overflowX: 'hidden' },
          '#root': { overflowX: 'hidden' },
          '::-webkit-scrollbar':        { width: 6, height: 6 },
          '::-webkit-scrollbar-track':  { background: 'transparent' },
          '::-webkit-scrollbar-thumb':  { background: scrollThumb, borderRadius: 3 },
          '::-webkit-scrollbar-thumb:hover': { background: scrollHover },
          // Make tables scroll horizontally on small screens instead of overflowing the viewport
          '.MuiTableContainer-root': { maxWidth: '100%', overflowX: 'auto' },
          // Prevent images / svg from forcing horizontal scroll on mobile
          'img, svg, video, canvas, picture': { maxWidth: '100%' },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: { textTransform: 'none', fontWeight: 600, borderRadius: 6, padding: '6px 14px', fontSize: '0.8125rem' },
          contained: {
            boxShadow: `0 1px 2px 0 ${dark ? 'rgba(0,0,0,0.4)' : 'rgba(0,0,0,0.08)'}`,
            '&:hover': { boxShadow: `0 2px 4px 0 ${dark ? 'rgba(0,0,0,0.5)' : 'rgba(0,0,0,0.12)'}` },
          },
          containedPrimary: {
            background: ACCENT.main,
            '&:hover': { background: ACCENT.dark },
          },
          outlined: {
            borderColor: border,
            color: text.primary,
            '&:hover': { borderColor: dark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)', backgroundColor: hoverBg },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: bg.paper,
            border: `1px solid ${border}`,
            boxShadow: dark ? 'none' : '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02)',
            borderRadius: 10,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: bg.paper,
            border: `1px solid ${border}`,
            boxShadow: dark ? 'none' : '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02)',
            borderRadius: 10,
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: dark ? 'rgba(10,10,12,0.85)' : 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(12px)',
            borderBottom: `1px solid ${border}`,
            boxShadow: 'none',
            color: text.primary,
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundImage: 'none',
            backgroundColor: dark ? '#0c0c0f' : '#ffffff',
            borderRight: `1px solid ${border}`,
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderBottom: `1px solid ${border}`,
            padding: '12px 16px',
            fontSize: '0.8125rem',
            color: text.primary,
            // Tighter padding on small screens so tables fit without crushing
            '@media (max-width:600px)': {
              padding: '10px 10px',
              fontSize: '0.75rem',
            },
          },
          head: {
            fontWeight: 600,
            color: text.secondary,
            fontSize: '0.6875rem',
            textTransform: 'uppercase' as const,
            letterSpacing: '0.06em',
            backgroundColor: dark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
            paddingTop: 10,
            paddingBottom: 10,
            whiteSpace: 'nowrap',
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            '&:hover': { backgroundColor: surfaceHover },
            '&.MuiTableRow-head:hover': { backgroundColor: 'transparent' },
          },
        },
      },
      MuiChip: {
        styleOverrides: { root: { fontWeight: 500, fontSize: '0.6875rem', borderRadius: 6, height: 24 } },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: 6,
              fontSize: '0.8125rem',
              '& fieldset': { borderColor: border },
              '&:hover fieldset': { borderColor: dark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.2)' },
              '&.Mui-focused fieldset': { borderColor: ACCENT.main, borderWidth: 1.5 },
            },
            '& .MuiInputLabel-root': { fontSize: '0.8125rem' },
          },
        },
      },
      MuiSelect: { styleOverrides: { root: { borderRadius: 6, fontSize: '0.8125rem' } } },
      MuiDialog: {
        styleOverrides: {
          paper: {
            backgroundColor: dark ? '#151518' : '#ffffff',
            border: `1px solid ${dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.1)'}`,
            borderRadius: 12,
            boxShadow: `0 24px 48px -12px ${dark ? 'rgba(0,0,0,0.6)' : 'rgba(0,0,0,0.15)'}`,
            // On phones the dialog should breathe to viewport edges, not float small
            '@media (max-width:600px)': {
              margin: 8,
              width: 'calc(100% - 16px)',
              maxWidth: 'calc(100% - 16px) !important',
              maxHeight: 'calc(100% - 16px)',
              borderRadius: 8,
            },
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
            fontSize: '0.8125rem',
            minHeight: 42,
            color: text.secondary,
            '&.Mui-selected': { color: text.primary, fontWeight: 600 },
          },
        },
      },
      MuiTabs: { styleOverrides: { indicator: { height: 2, borderRadius: 1, backgroundColor: ACCENT.main } } },
      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: 8, border: '1px solid', fontSize: '0.8125rem' },
          standardError:   { backgroundColor: alpha('#df1b41', dark ? 0.08 : 0.04), borderColor: alpha('#df1b41', 0.2), color: dark ? '#f8a4b8' : '#9e1234' },
          standardWarning: { backgroundColor: alpha('#e87f17', dark ? 0.08 : 0.04), borderColor: alpha('#e87f17', 0.2), color: dark ? '#fcc57a' : '#8a4d0a' },
          standardInfo:    { backgroundColor: alpha('#3b82f6', dark ? 0.08 : 0.04), borderColor: alpha('#3b82f6', 0.2), color: dark ? '#93c5fd' : '#1e4fad' },
          standardSuccess: { backgroundColor: alpha('#0ea371', dark ? 0.08 : 0.04), borderColor: alpha('#0ea371', 0.2), color: dark ? '#6ee7b7' : '#065f46' },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: { backgroundColor: dark ? '#27272a' : '#1a1f36', color: '#ffffff', border: `1px solid ${dark ? 'rgba(255,255,255,0.08)' : 'transparent'}`, fontSize: '0.6875rem', borderRadius: 6 },
        },
      },
      MuiMenu: {
        styleOverrides: {
          paper: {
            backgroundColor: dark ? '#151518' : '#ffffff',
            border: `1px solid ${dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
            borderRadius: 8,
            boxShadow: `0 8px 30px ${dark ? 'rgba(0,0,0,0.5)' : 'rgba(0,0,0,0.12)'}`,
          },
        },
      },
      MuiMenuItem: {
        styleOverrides: {
          root: { fontSize: '0.8125rem', borderRadius: 4, margin: '2px 6px', padding: '7px 10px', '&:hover': { backgroundColor: hoverBg } },
        },
      },
      MuiIconButton: {
        styleOverrides: { root: { borderRadius: 6, '&:hover': { backgroundColor: hoverBg } } },
      },
      MuiTablePagination: {
        styleOverrides: {
          root: {
            borderTop: `1px solid ${border}`,
            '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': { fontSize: '0.75rem' },
            // On phones hide the rows-per-page label (the dropdown stays) so toolbar fits
            '@media (max-width:600px)': {
              '& .MuiTablePagination-selectLabel': { display: 'none' },
              '& .MuiTablePagination-toolbar': { paddingLeft: 8, paddingRight: 8, minHeight: 44 },
              '& .MuiTablePagination-actions': { marginLeft: 4 },
            },
          },
        },
      },
      MuiFormControl: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: 6,
              '& fieldset': { borderColor: border },
              '&:hover fieldset': { borderColor: dark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.2)' },
            },
          },
        },
      },
      MuiSwitch: {
        styleOverrides: {
          root: {
            '& .MuiSwitch-switchBase.Mui-checked': { color: ACCENT.main },
            '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: ACCENT.main },
          },
        },
      },
    },
  });
}

// ── Suspense fallback ──────────────────────────────────────────────
const PageFallback: React.FC = () => (
  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
    <CircularProgress size={32} thickness={3} />
  </Box>
);

// ── i18n bridge — pulls tier from AuthContext into the I18nProvider ─
const TierAwareI18n: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { tier } = useAuth();
  return <I18nProvider tier={tier}>{children}</I18nProvider>;
};

// ── Route tree ─────────────────────────────────────────────────────
const ThemedApp: React.FC = () => {
  const { mode } = useThemeMode();
  const theme = useMemo(() => buildTheme(mode), [mode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <TierAwareI18n>
          <WalkthroughProvider>
            <Suspense fallback={<PageFallback />}>
              <Routes>
              <Route path="/login" element={<Login />} />

              {/* ── Protected layout shell ── */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                {/* Core */}
                <Route path="/"             element={<Dashboard />} />
                <Route path="/agents"       element={<AgentList />} />
                <Route path="/agents/:agentId" element={<AgentDetail />} />
                <Route path="/policies"     element={<PolicyList />} />
                <Route path="/policies/create" element={<PolicyEditor />} />
                <Route path="/policies/:policyId/edit" element={<PolicyEditor />} />
                <Route path="/audit"        element={<AuditLogs />} />
                <Route path="/alerts"       element={<Alerts />} />
                <Route
                  path="/users"
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.SYSTEM_ADMIN, UserRole.ADMIN]}>
                      <Users />
                    </ProtectedRoute>
                  }
                />

                {/* Clinical Governance */}
                <Route path="/clinical/model-cards"        element={<ModelCardList />} />
                <Route path="/clinical/model-cards/new"    element={<ModelCardEditor />} />
                <Route path="/clinical/model-cards/:id"    element={<ModelCardEditor />} />
                <Route path="/clinical/bias-audits"        element={<BiasAuditList />} />
                <Route path="/clinical/bias-audits/:id"    element={<BiasAuditDetail />} />
                <Route path="/clinical/drift"              element={<DriftMonitor />} />
                <Route path="/clinical/hitl"               element={<HITLQueue />} />
                <Route path="/clinical/hitl/:id"           element={<HITLReviewDetail />} />

                {/* Admin Governance */}
                <Route path="/admin/shadow-ai"             element={<ShadowAIDiscovery />} />
                <Route path="/admin/scribe-audits"         element={<ScribeAuditList />} />
                <Route path="/transparency"                element={<TransparencyPortal />} />

                {/* Financial */}
                <Route path="/finance/prior-auth"          element={<PriorAuthTrail />} />
                <Route path="/finance/revenue-cycle"       element={<RevenueCycleAudit />} />

                {/* Regulatory */}
                <Route path="/regulatory/technical-files"  element={<TechnicalFiles />} />
                <Route path="/regulatory/adverse-events"   element={<AdverseEvents />} />
                <Route path="/regulatory/pms-reports"      element={<PostMarketSurveillance />} />

                {/* Risk */}
                <Route path="/risk/portfolio"              element={<RiskPortfolio />} />
                <Route path="/risk/scores/:modelId"        element={<RiskScoreDetail />} />

                {/* ── Clinic-tier surface (CRIT-012: tier-gated) ── */}
                <Route path="/clinic"                       element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicDashboard /></ProtectedRoute>} />
                <Route path="/clinic/onboarding"            element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicOnboarding /></ProtectedRoute>} />
                <Route path="/clinic/tools"                 element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicToolList /></ProtectedRoute>} />
                <Route path="/clinic/tools/new"             element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicToolEditor /></ProtectedRoute>} />
                <Route path="/clinic/tools/:id"             element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicToolEditor /></ProtectedRoute>} />
                <Route path="/clinic/policies"              element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicPolicyLibrary /></ProtectedRoute>} />
                <Route path="/clinic/alerts"                element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicAlertCenter /></ProtectedRoute>} />
                <Route path="/clinic/shadow-ai"             element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicShadowAi /></ProtectedRoute>} />
                <Route path="/clinic/reports"               element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicReports /></ProtectedRoute>} />
                <Route path="/clinic/settings/practice"     element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicPracticeSet /></ProtectedRoute>} />
                <Route path="/clinic/settings/compliance"   element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicComplianceSet /></ProtectedRoute>} />
                <Route path="/clinic/settings/billing"      element={<ProtectedRoute requiredTiers={CLINIC_TIERS}><ClinicBillingSet /></ProtectedRoute>} />

                {/* Settings */}
                <Route
                  path="/settings/organization"
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.SYSTEM_ADMIN, UserRole.ADMIN]}>
                      <OrganizationSettings />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/settings/risk"
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.SYSTEM_ADMIN, UserRole.ADMIN]}>
                      <RiskConfiguration />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/settings/hipaa"
                  element={
                    <ProtectedRoute requiredRoles={[UserRole.SYSTEM_ADMIN, UserRole.ADMIN]}>
                      <HIPAAConfiguration />
                    </ProtectedRoute>
                  }
                />
              </Route>

                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </WalkthroughProvider>
          </TierAwareI18n>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
};

const App: React.FC = () => (
  <ThemeModeProvider>
    <ThemedApp />
  </ThemeModeProvider>
);

export default App;
