import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
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

// Create MUI theme
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
      dark: '#115293',
    },
    secondary: {
      main: '#dc004e',
    },
    success: {
      main: '#2e7d32',
    },
    warning: {
      main: '#ed6c02',
    },
    error: {
      main: '#d32f2f',
    },
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
        },
      },
    },
  },
});

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />

            {/* Protected routes */}
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

            {/* Catch all - redirect to home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default App;
