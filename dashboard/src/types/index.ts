// User and Authentication Types
export enum UserRole {
  ADMIN = 'admin',
  ANALYST = 'analyst',
  VIEWER = 'viewer',
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  full_name?: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  last_login?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// Agent Types
export interface Agent {
  id: number;
  agent_id: string;
  name: string;
  description?: string;
  status: 'active' | 'inactive' | 'suspended';
  created_at: string;
  last_active?: string;
  systems_accessed?: string[];
  metadata?: Record<string, any>;
}

export interface AgentListResponse {
  agents: Agent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AgentActivityMetrics {
  agent_id: string;
  total_actions: number;
  blocked_actions: number;
  allowed_actions: number;
  systems_accessed: string[];
  first_seen: string;
  last_active: string;
  status: string;
}

// Policy Types
export interface Policy {
  id: string;
  name: string;
  description?: string;
  policy_type: string;
  rules: PolicyRule[];
  applies_to: string[];
  enabled: boolean;
  priority?: number;
  created_at: string;
  updated_at?: string;
  created_by?: string;
}

export interface PolicyRule {
  id?: string;
  description?: string;
  conditions: PolicyCondition[];
  action: 'allow' | 'block' | 'require_approval';
  metadata?: Record<string, any>;
}

export interface PolicyCondition {
  field: string;
  operator: string;
  value: any;
}

export interface PolicyListResponse {
  policies: Policy[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PolicyCreate {
  name: string;
  description?: string;
  policy_type: string;
  rules: PolicyRule[];
  applies_to: string[];
  enabled?: boolean;
  priority?: number;
}

export interface PolicyUpdate {
  name?: string;
  description?: string;
  policy_type?: string;
  rules?: PolicyRule[];
  applies_to?: string[];
  enabled?: boolean;
  priority?: number;
}

// Audit Log Types
export interface AuditLog {
  id: number;
  timestamp: string;
  agent_id: string;
  user_id?: string;
  system_accessed: string;
  action: string;
  data_touched?: string;
  policy_decision: 'allow' | 'block' | 'require_approval';
  policy_id?: number;
  details?: Record<string, any>;
}

// Alert Types
export interface Alert {
  id: number;
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  alert_type: string;
  agent_id?: string;
  policy_id?: number;
  message: string;
  details?: Record<string, any>;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
}

// Dashboard Metrics
export interface RecentAlert {
  id: number;
  timestamp: string;
  severity: string;
  alert_type: string;
  message: string;
  agent_id?: string;
  policy_id?: number;
}

export interface TopAgent {
  agent_id: string;
  action_count: number;
}

export interface PolicyViolation {
  policy_name: string;
  count: number;
}

export interface SystemAccess {
  system: string;
  access_count: number;
}

export interface ActivityTimelineItem {
  timestamp: string;
  count: number;
}

export interface RecentBlockedAction {
  id: number;
  timestamp: string;
  agent_id: string;
  action: string;
  system_accessed: string;
  policy_id?: number;
}

export interface DashboardMetrics {
  active_agents: number;
  total_actions: number;
  blocked_actions: number;
  money_saved: number;
  money_spent: number;
  recent_alerts: RecentAlert[];
  top_agents: TopAgent[];
  policy_violations: PolicyViolation[];
  systems_accessed: SystemAccess[];
  activity_timeline: ActivityTimelineItem[];
  recent_blocked_actions: RecentBlockedAction[];
  alerts_by_severity: Record<string, number>;
}

// API Response Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}
