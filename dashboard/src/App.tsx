import React, { useMemo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline, alpha, type PaletteMode } from '@mui/material';
import { ThemeModeProvider, useThemeMode } from '@/contexts/ThemeContext';
import { AuthProvider } from '@/contexts/AuthContext';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import Login from '@/components/auth/Login';
import AppLayout from '@/components/layout/AppLayout';
import Dashboard from '@/pages/Dashboard';
import AgentList from '@/pages/AgentList';
import AgentDetail from '@/pages/AgentDetail';
import PolicyList from '@/pages/PolicyList';
import PolicyEditor from '@/pages/PolicyEditor';
import AuditLogs from '@/pages/AuditLogs';
import Alerts from '@/pages/Alerts';
import Users from '@/pages/Users';
import { UserRole } from '@/types';

const ACCENT = { main: '#635bff', light: '#7a73ff', dark: '#5046e5' };

function buildTheme(mode: PaletteMode) {
  const dark = mode === 'dark';

  const bg   = dark ? { default: '#0a0a0c', paper: '#111114' } : { default: '#f6f8fa', paper: '#ffffff' };
  const text = dark ? { primary: '#f0f2f5', secondary: '#8b8fa3' } : { primary: '#1a1f36', secondary: '#697386' };
  const border = dark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.08)';
  const hoverBg = dark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.03)';
  const surfaceHover = dark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.015)';
  const scrollThumb = dark ? '#2a2a2e' : '#c8c8cc';
  const scrollHover = dark ? '#3f3f44' : '#a0a0a6';

  return createTheme({
    palette: {
      mode,
      primary: ACCENT,
      secondary: { main: '#a78bfa', light: '#c4b5fd', dark: '#7c3aed' },
      success: { main: '#0ea371', light: '#3ecf8e', dark: '#067a55' },
      warning: { main: '#e87f17', light: '#f5a623', dark: '#c26a0a' },
      error: { main: '#df1b41', light: '#f04662', dark: '#b31535' },
      info: { main: '#3b82f6', light: '#60a5fa', dark: '#2563eb' },
      background: bg,
      text,
      divider: border,
    },
    typography: {
      fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      h1: { fontWeight: 700, letterSpacing: '-0.025em', fontSize: '2rem' },
      h2: { fontWeight: 700, letterSpacing: '-0.02em', fontSize: '1.5rem' },
      h3: { fontWeight: 600, letterSpacing: '-0.02em', fontSize: '1.25rem' },
      h4: { fontWeight: 600, letterSpacing: '-0.015em', fontSize: '1.125rem' },
      h5: { fontWeight: 600, letterSpacing: '-0.01em', fontSize: '1rem' },
      h6: { fontWeight: 600, fontSize: '0.875rem' },
      subtitle1: { fontWeight: 500, fontSize: '0.9375rem', color: text.secondary },
      subtitle2: { fontWeight: 500, fontSize: '0.8125rem', color: text.secondary },
      body1: { fontSize: '0.875rem', lineHeight: 1.65, color: text.primary },
      body2: { fontSize: '0.8125rem', lineHeight: 1.55, color: text.secondary },
      caption: { fontSize: '0.6875rem', letterSpacing: '0.02em', color: text.secondary },
      button: { fontWeight: 600, fontSize: '0.8125rem', letterSpacing: '0.01em' },
    },
    shape: { borderRadius: 8 },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: { backgroundColor: bg.default },
          '::-webkit-scrollbar': { width: 6, height: 6 },
          '::-webkit-scrollbar-track': { background: 'transparent' },
          '::-webkit-scrollbar-thumb': { background: scrollThumb, borderRadius: 3 },
          '::-webkit-scrollbar-thumb:hover': { background: scrollHover },
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
        styleOverrides: {
          root: { fontWeight: 500, fontSize: '0.6875rem', borderRadius: 6, height: 24 },
        },
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
          standardError: { backgroundColor: alpha('#df1b41', dark ? 0.08 : 0.04), borderColor: alpha('#df1b41', 0.2), color: dark ? '#f8a4b8' : '#9e1234' },
          standardWarning: { backgroundColor: alpha('#e87f17', dark ? 0.08 : 0.04), borderColor: alpha('#e87f17', 0.2), color: dark ? '#fcc57a' : '#8a4d0a' },
          standardInfo: { backgroundColor: alpha('#3b82f6', dark ? 0.08 : 0.04), borderColor: alpha('#3b82f6', 0.2), color: dark ? '#93c5fd' : '#1e4fad' },
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
        styleOverrides: { root: { borderTop: `1px solid ${border}`, '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': { fontSize: '0.75rem' } } },
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

const ThemedApp: React.FC = () => {
  const { mode } = useThemeMode();
  const theme = useMemo(() => buildTheme(mode), [mode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<Dashboard />} />
              <Route path="/agents" element={<AgentList />} />
              <Route path="/agents/:agentId" element={<AgentDetail />} />
              <Route path="/policies" element={<PolicyList />} />
              <Route path="/policies/create" element={<PolicyEditor />} />
              <Route path="/policies/:policyId/edit" element={<PolicyEditor />} />
              <Route path="/audit" element={<AuditLogs />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route
                path="/users"
                element={
                  <ProtectedRoute requiredRoles={[UserRole.ADMIN]}>
                    <Users />
                  </ProtectedRoute>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
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
