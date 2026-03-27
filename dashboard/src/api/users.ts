import apiClient from './client';

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  role: string;
  full_name: string | null;
  created_at: string;
  updated_at: string;
  last_login: string | null;
  is_active: boolean;
}

export interface UserListResponse {
  users: UserResponse[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UserCreateRequest {
  username: string;
  email: string;
  password: string;
  role?: string;
  full_name?: string;
}

export interface UserUpdateRequest {
  email?: string;
  password?: string;
  role?: string;
  full_name?: string;
  is_active?: boolean;
}

const usersApi = {
  async listUsers(params?: {
    role_filter?: string;
    is_active?: boolean;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<UserListResponse> {
    return apiClient.get('/v1/users', params);
  },

  async getUser(userId: string): Promise<UserResponse> {
    return apiClient.get(`/v1/users/${userId}`);
  },

  async createUser(data: UserCreateRequest): Promise<UserResponse> {
    return apiClient.post('/v1/users', data);
  },

  async updateUser(userId: string, data: UserUpdateRequest): Promise<UserResponse> {
    return apiClient.put(`/v1/users/${userId}`, data);
  },

  async deleteUser(userId: string): Promise<void> {
    return apiClient.delete(`/v1/users/${userId}`);
  },

  async changePassword(userId: string, data: { current_password: string; new_password: string }): Promise<UserResponse> {
    return apiClient.post(`/v1/users/${userId}/change-password`, data);
  },

  async assignRole(data: { user_id: string; role: string }): Promise<UserResponse> {
    return apiClient.post('/v1/users/assign-role', data);
  },
};

export default usersApi;
