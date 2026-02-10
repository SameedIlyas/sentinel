/**
 * API service for alert management
 */

import apiClient from './client';

export interface AlertRule {
  id: string;
  policy_type: string | null;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  conditions: Record<string, any> | null;
  slack_webhook_url: string | null;
  enabled: boolean;
  created_at: string;
}

export interface AlertRuleCreate {
  policy_type?: 'data_access' | 'financial' | 'data_protection' | 'system_access' | null;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  conditions?: Record<string, any>;
  slack_webhook_url?: string;
  enabled?: boolean;
}

export interface Alert {
  id: string;
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  alert_type: string;
  agent_id: string;
  description: string;
  audit_log_id: string | null;
  acknowledged: boolean;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
}

export interface AlertListResponse {
  alerts: Alert[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AlertConfigRequest {
  global_slack_webhook?: string;
  alert_rules?: AlertRuleCreate[];
  deduplication_window_seconds?: number;
}

export interface SlackConfig {
  webhook_url: string;
  channel?: string;
  enabled: boolean;
}

const alertsApi = {
  /**
   * Configure alert rules and Slack webhook
   */
  async configureAlerts(config: AlertConfigRequest): Promise<{
    message: string;
    global_webhook_configured: boolean;
    rules_created: number;
    rules: AlertRule[];
  }> {
    return apiClient.post('/v1/alerts/configure', config);
  },

  /**
   * List alerts with filtering and pagination
   */
  async listAlerts(params?: {
    alert_type?: string;
    severity?: string;
    acknowledged?: boolean;
    page?: number;
    page_size?: number;
  }): Promise<AlertListResponse> {
    return apiClient.get('/v1/alerts', params);
  },

  /**
   * Get a specific alert by ID
   */
  async getAlert(alertId: string): Promise<Alert> {
    return apiClient.get(`/v1/alerts/${alertId}`);
  },

  /**
   * Acknowledge an alert
   */
  async acknowledgeAlert(alertId: string, acknowledgedBy: string): Promise<Alert> {
    return apiClient.post(`/v1/alerts/${alertId}/acknowledge`, {
      acknowledged_by: acknowledgedBy,
    });
  },

  /**
   * Test Slack webhook configuration
   */
  async testSlackWebhook(config: SlackConfig): Promise<{
    success: boolean;
    message: string;
  }> {
    return apiClient.post('/v1/alerts/test', config);
  },

  /**
   * List all alert rules
   */
  async listAlertRules(enabledOnly: boolean = false): Promise<AlertRule[]> {
    return apiClient.get('/v1/alerts/rules/list', { enabled_only: enabledOnly });
  },
};

export default alertsApi;
