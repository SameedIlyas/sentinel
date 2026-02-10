import apiClient from './client';
import { DashboardMetrics } from '@/types';

/**
 * Dashboard API service
 * Provides methods for fetching dashboard metrics and statistics
 */
export const dashboardApi = {
  /**
   * Get dashboard metrics
   * Returns aggregated statistics including active agents, actions, financial metrics, etc.
   */
  async getMetrics(): Promise<DashboardMetrics> {
    return apiClient.get<DashboardMetrics>('/v1/dashboard/metrics');
  },
};

export default dashboardApi;
