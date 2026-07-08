import { fetchApi } from './client';

export interface UserResponse {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface LoginResponse {
  tokens: {
    access_token: string;
    token_type: string;
  };
  user: UserResponse;
}

export interface MessageResponse {
  message: string;
}

export const authApi = {
  register: async (data: Record<string, any>): Promise<LoginResponse> => {
    return fetchApi<LoginResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  login: async (email: string, password: string): Promise<{ access_token: string }> => {
    const response = await fetchApi<LoginResponse>('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });
    // Assuming refresh token handling logic is managed elsewhere, but login returns tokens.
    // For now we just return access_token as before to keep compatibility, though we could return the whole response.
    return { access_token: response.tokens.access_token };
  },

  refresh: async (refreshToken: string): Promise<{ access_token: string, token_type: string }> => {
    return fetchApi<{ access_token: string, token_type: string }>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  logout: async (refreshToken: string): Promise<void> => {
    return fetchApi<void>('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  logoutAll: async (): Promise<MessageResponse> => {
    return fetchApi<MessageResponse>('/auth/logout-all', {
      method: 'POST',
    });
  },

  getCurrentUser: async (): Promise<UserResponse> => {
    return fetchApi<UserResponse>('/auth/me');
  },

  requestPasswordReset: async (email: string): Promise<MessageResponse> => {
    return fetchApi<MessageResponse>('/auth/password-reset/request', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  confirmPasswordReset: async (data: Record<string, any>): Promise<MessageResponse> => {
    return fetchApi<MessageResponse>('/auth/password-reset/confirm', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  changePassword: async (data: Record<string, any>): Promise<MessageResponse> => {
    return fetchApi<MessageResponse>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
};
