import apiClient from './client';
import { Agent, AgentActivityMetrics, AgentListResponse } from '@/types';

/**
 * Agents API service
 * Provides methods for managing and retrieving agent information
 */
export const agentsApi = {
  /**
   * List all agents with optional filtering and pagination
   */
  async listAgents(params?: {
    status_filter?: 'active' | 'inactive' | 'suspended';
    owner_user_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<AgentListResponse> {
    return apiClient.get<AgentListResponse>('/v1/agents', params);
  },

  /**
   * Get a specific agent by ID
   */
  async getAgent(agentId: string): Promise<Agent> {
    return apiClient.get<Agent>(`/v1/agents/${agentId}`);
  },

  /**
   * Get activity metrics for a specific agent
   */
  async getAgentMetrics(agentId: string): Promise<AgentActivityMetrics> {
    return apiClient.get<AgentActivityMetrics>(`/v1/agents/${agentId}/metrics`);
  },

  /**
   * Update an agent's information
   */
  async updateAgent(
    agentId: string,
    data: {
      name?: string;
      description?: string;
      status?: 'active' | 'inactive' | 'suspended';
      metadata?: Record<string, any>;
    }
  ): Promise<Agent> {
    return apiClient.put<Agent>(`/v1/agents/${agentId}`, data);
  },
};

export default agentsApi;
