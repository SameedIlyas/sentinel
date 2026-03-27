import apiClient from './client';
import { AuditLog, AuditLogListResponse } from '@/types';

/**
 * Audit Logs API service
 * Provides methods for querying and exporting audit logs
 */
export const auditLogsApi = {
  /**
   * List audit logs with optional filtering and pagination
   */
  async listAuditLogs(params?: {
    page?: number;
    page_size?: number;
    filter_agent_id?: string;
    filter_user_id?: string;
    filter_tool_name?: string;
    filter_system?: string;
    filter_decision?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
  }): Promise<AuditLogListResponse> {
    return apiClient.get<AuditLogListResponse>('/v1/audit/logs', params);
  },

  /**
   * Get a specific audit log by ID
   */
  async getAuditLog(logId: string): Promise<AuditLog> {
    return apiClient.get<AuditLog>(`/v1/audit/logs/${logId}`);
  },

  /**
   * Export audit logs to JSON
   */
  async exportToJson(params?: {
    filter_agent_id?: string;
    filter_user_id?: string;
    filter_tool_name?: string;
    filter_system?: string;
    filter_decision?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
  }): Promise<Blob> {
    const response = await apiClient.getBlob('/v1/audit/logs/export', { ...params, format: 'json' });
    return response;
  },

  /**
   * Export audit logs to CSV
   */
  async exportToCsv(params?: {
    filter_agent_id?: string;
    filter_user_id?: string;
    filter_tool_name?: string;
    filter_system?: string;
    filter_decision?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
  }): Promise<Blob> {
    const response = await apiClient.getBlob('/v1/audit/logs/export', { ...params, format: 'csv' });
    return response;
  },
};

export default auditLogsApi;
