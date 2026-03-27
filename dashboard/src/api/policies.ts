import apiClient from './client';
import { Policy, PolicyListResponse, PolicyCreate, PolicyUpdate } from '@/types';

/**
 * Policies API service
 * Provides methods for managing policies
 */
export const policiesApi = {
  /**
   * List all policies with optional filtering and pagination
   */
  async listPolicies(params?: {
    policy_type?: string;
    enabled?: boolean;
    applies_to_agent?: string;
    page?: number;
    page_size?: number;
  }): Promise<PolicyListResponse> {
    return apiClient.get<PolicyListResponse>('/v1/policies', params);
  },

  /**
   * Get a specific policy by ID
   */
  async getPolicy(policyId: string): Promise<Policy> {
    return apiClient.get<Policy>(`/v1/policies/${policyId}`);
  },

  /**
   * Create a new policy
   */
  async createPolicy(data: PolicyCreate): Promise<Policy> {
    return apiClient.post<Policy>('/v1/policies', data);
  },

  /**
   * Update an existing policy
   */
  async updatePolicy(policyId: string, data: PolicyUpdate): Promise<Policy> {
    return apiClient.put<Policy>(`/v1/policies/${policyId}`, data);
  },

  /**
   * Delete a policy
   */
  async deletePolicy(policyId: string): Promise<{ success: boolean; message: string }> {
    return apiClient.delete(`/v1/policies/${policyId}`);
  },

  /**
   * Toggle policy enabled status
   */
  async togglePolicy(policyId: string, enabled: boolean): Promise<Policy> {
    return apiClient.put<Policy>(`/v1/policies/${policyId}`, { enabled });
  },
};

export default policiesApi;
