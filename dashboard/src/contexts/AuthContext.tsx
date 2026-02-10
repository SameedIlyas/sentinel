import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User, LoginRequest, UserRole } from '@/types';
import apiClient from '@/api/client';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (roles: UserRole | UserRole[]) => boolean;
  hasPermission: (resource: string, action: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

// Permission matrix matching backend ROLE_PERMISSIONS
const ROLE_PERMISSIONS: Record<UserRole, Record<string, string[]>> = {
  [UserRole.ADMIN]: {
    policies: ['create', 'read', 'update', 'delete'],
    agents: ['create', 'read', 'update', 'delete'],
    audit_logs: ['read', 'export'],
    alerts: ['read', 'acknowledge'],
    users: ['create', 'read', 'update', 'delete'],
    system: ['configure'],
  },
  [UserRole.ANALYST]: {
    policies: ['read'],
    agents: ['read'],
    audit_logs: ['read', 'export'],
    alerts: ['read', 'acknowledge'],
    users: [],
    system: [],
  },
  [UserRole.VIEWER]: {
    policies: ['read'],
    agents: ['read'],
    audit_logs: ['read'],
    alerts: ['read'],
    users: [],
    system: [],
  },
};

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if user is already authenticated on mount
    const initAuth = async () => {
      try {
        if (apiClient.isAuthenticated()) {
          const currentUser = await apiClient.validateToken();
          setUser(currentUser);
        }
      } catch (error) {
        console.error('Failed to validate token:', error);
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
    const roleArray = Array.isArray(roles) ? roles : [roles];
    return roleArray.includes(user.role);
  };

  const hasPermission = (resource: string, action: string): boolean => {
    if (!user) return false;
    const permissions = ROLE_PERMISSIONS[user.role];
    if (!permissions || !permissions[resource]) return false;
    return permissions[resource].includes(action);
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    hasRole,
    hasPermission,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
