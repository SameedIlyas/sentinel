import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User, LoginRequest, UserRole, TierKey, resolveTier } from '@/types';
import {
  getClinicProductRole,
  type ProductRole,
} from '@/auth/clinicProductRole';
import apiClient from '@/api/client';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  /** Convenience accessor — `user?.tier ?? 'enterprise'`. */
  tier: TierKey;
  /**
   * R2 — Projected product role:
   *  - On clinic tiers, `'admin' | 'staff'` (eight backend roles collapsed
   *    to two for UX).
   *  - On enterprise tier, the backend `UserRole` itself (identity).
   *  - `null` when no user is authenticated.
   *
   * Source of truth for *access* is still backend RBAC
   * (`policy_engine/auth/rbac.py`). This is a presentation projection only.
   */
  productRole: ProductRole | null;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (roles: UserRole | UserRole[]) => boolean;
  hasPermission: (resource: string, action: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};

// Permission matrix — mirrors backend ROLE_PERMISSIONS
const ROLE_PERMISSIONS: Record<UserRole, Record<string, string[]>> = {
  [UserRole.SYSTEM_ADMIN]: {
    policies: ['create', 'read', 'update', 'delete'],
    agents: ['create', 'read', 'update', 'delete'],
    audit_logs: ['read', 'export'],
    alerts: ['create', 'read', 'update', 'acknowledge', 'configure'],
    users: ['create', 'read', 'update', 'delete'],
    organizations: ['create', 'read', 'update', 'delete'],
    model_cards: ['create', 'read', 'update', 'delete'],
    bias_audits: ['create', 'read', 'update', 'delete'],
    drift_detection: ['create', 'read', 'update', 'delete'],
    hitl_reviews: ['create', 'read', 'update', 'delete'],
    shadow_ai: ['create', 'read', 'update', 'delete'],
    scribe_audits: ['create', 'read', 'update', 'delete'],
    transparency: ['create', 'read', 'update', 'delete'],
    prior_auth: ['create', 'read', 'update', 'delete'],
    revenue_cycle: ['create', 'read', 'update', 'delete'],
    technical_files: ['create', 'read', 'update', 'delete'],
    post_market: ['create', 'read', 'update', 'delete'],
    risk_scores: ['create', 'read', 'update', 'delete'],
  },
  [UserRole.ADMIN]: {
    policies: ['create', 'read', 'update', 'delete'],
    agents: ['create', 'read', 'update', 'delete'],
    audit_logs: ['read', 'export'],
    alerts: ['create', 'read', 'update', 'acknowledge', 'configure'],
    users: ['create', 'read', 'update', 'delete'],
    model_cards: ['create', 'read', 'update', 'delete'],
    bias_audits: ['create', 'read', 'update'],
    drift_detection: ['read', 'update'],
    hitl_reviews: ['create', 'read', 'update'],
    shadow_ai: ['read'],
    scribe_audits: ['read'],
    transparency: ['read'],
    prior_auth: ['create', 'read', 'update'],
    revenue_cycle: ['read'],
    technical_files: ['create', 'read', 'update'],
    post_market: ['read'],
    risk_scores: ['create', 'read', 'update', 'delete'],
  },
  [UserRole.CMIO]: {
    policies: ['create', 'read', 'update'],
    agents: ['read', 'update'],
    audit_logs: ['read', 'export'],
    alerts: ['read', 'acknowledge'],
    users: ['read'],
    model_cards: ['create', 'read', 'update'],
    bias_audits: ['read'],
    drift_detection: ['read'],
    hitl_reviews: ['create', 'read', 'update'],
    risk_scores: ['read'],
    transparency: ['read'],
  },
  [UserRole.DATA_SCIENTIST]: {
    policies: ['read'],
    agents: ['read'],
    audit_logs: ['read'],
    alerts: ['read'],
    model_cards: ['create', 'read', 'update'],
    bias_audits: ['create', 'read', 'update'],
    drift_detection: ['create', 'read', 'update'],
    risk_scores: ['create', 'read', 'update'],
    technical_files: ['create', 'read', 'update'],
  },
  [UserRole.COMPLIANCE_OFFICER]: {
    policies: ['read', 'update'],
    agents: ['read'],
    audit_logs: ['read', 'export'],
    alerts: ['read', 'acknowledge'],
    users: ['read'],
    model_cards: ['read'],
    bias_audits: ['read'],
    drift_detection: ['read'],
    transparency: ['read'],
    post_market: ['read'],
    risk_scores: ['read'],
    technical_files: ['read'],
    prior_auth: ['read'],
    revenue_cycle: ['read'],
  },
  [UserRole.CLINICAL_USER]: {
    policies: ['read'],
    agents: ['read'],
    audit_logs: ['read'],
    alerts: ['read'],
    hitl_reviews: ['create', 'read', 'update'],
    prior_auth: ['create', 'read'],
    risk_scores: ['read'],
    scribe_audits: ['read'],
    shadow_ai: ['read'],
  },
  [UserRole.ANALYST]: {
    policies: ['read'],
    agents: ['read'],
    audit_logs: ['read', 'export'],
    alerts: ['read', 'acknowledge'],
    risk_scores: ['read'],
  },
  [UserRole.VIEWER]: {
    policies: ['read'],
    agents: ['read'],
    audit_logs: ['read'],
    alerts: ['read'],
  },
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      try {
        if (apiClient.isAuthenticated()) {
          const currentUser = await apiClient.validateToken();
          setUser(currentUser);
        }
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };
    initAuth();
  }, []);

  const login = async (credentials: LoginRequest) => {
    setIsLoading(true);
    try {
      const response = await apiClient.login(credentials);
      setUser(response.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await apiClient.logout();
    } finally {
      setUser(null);
      setIsLoading(false);
    }
  };

  const hasRole = (roles: UserRole | UserRole[]): boolean => {
    if (!user) return false;
    const arr = Array.isArray(roles) ? roles : [roles];
    return arr.includes(user.role);
  };

  const hasPermission = (resource: string, action: string): boolean => {
    if (!user) return false;
    const perms = ROLE_PERMISSIONS[user.role];
    return perms?.[resource]?.includes(action) ?? false;
  };

  const tier: TierKey = resolveTier(user?.tier);
  const productRole: ProductRole | null = user
    ? getClinicProductRole(user.role, tier)
    : null;

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        tier,
        productRole,
        login,
        logout,
        hasRole,
        hasPermission,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
