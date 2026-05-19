import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { useAuth } from '@/contexts/AuthContext';
import { UserRole, TierKey } from '@/types';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: UserRole[];
  requiredPermission?: {
    resource: string;
    action: string;
  };
  /**
   * CRIT-012 — only render the children for these product tiers.
   * Cross-tier callers see AccessDenied. Defence-in-depth only — the
   * authoritative tier check lives on the corresponding /v1/clinic/*
   * API routes server-side (require_clinic_tier dependency).
   */
  requiredTiers?: TierKey[];
}

const AccessDenied: React.FC<{ message?: string }> = ({ message }) => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      p: 3,
    }}
  >
    <Box sx={{ textAlign: 'center' }}>
      <h1>Access Denied</h1>
      <p>{message ?? 'You do not have permission to access this page.'}</p>
    </Box>
  </Box>
);

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRoles,
  requiredPermission,
  requiredTiers,
}) => {
  const { isAuthenticated, isLoading, hasRole, hasPermission, tier } =
    useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRoles && requiredRoles.length > 0) {
    if (!hasRole(requiredRoles)) {
      return <AccessDenied />;
    }
  }

  if (requiredTiers && requiredTiers.length > 0) {
    if (!requiredTiers.includes(tier)) {
      return (
        <AccessDenied
          message="This page is only available to clinic-tier organizations."
        />
      );
    }
  }

  if (requiredPermission) {
    const { resource, action } = requiredPermission;
    if (!hasPermission(resource, action)) {
      return (
        <AccessDenied
          message={`You do not have the required permission (${resource}:${action}) to access this page.`}
        />
      );
    }
  }

  return <>{children}</>;
};

export default ProtectedRoute;
