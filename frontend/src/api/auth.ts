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

export const authApi = {
  login: async (email: string, password: string): Promise<{ access_token: string }> => {
    const response = await fetchApi<LoginResponse>('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });
    return { access_token: response.tokens.access_token };
  },

  getCurrentUser: async (): Promise<UserResponse> => {
    return fetchApi<UserResponse>('/auth/me');
  }
};
