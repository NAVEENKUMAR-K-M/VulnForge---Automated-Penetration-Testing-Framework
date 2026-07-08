import { fetchApi } from './client';

export interface ScanProfile {
  id: string;
  name: string;
  description: string | null;
  profile_type: string;
  is_default: boolean;
  enabled_plugins: string[];
  plugin_configs: Record<string, any>;
  created_at: string;
}

export interface ScanProfileCreate {
  name: string;
  description?: string;
  profile_type: string;
  is_default?: boolean;
  enabled_plugins?: string[];
  plugin_configs?: Record<string, any>;
}

export const scanProfilesApi = {
  list: async (skip = 0, limit = 100): Promise<ScanProfile[]> => {
    const res = await fetchApi<{ items: ScanProfile[] }>(`/scan-profiles/?skip=${skip}&limit=${limit}`);
    return res.items;
  },

  get: async (id: string): Promise<ScanProfile> => {
    return fetchApi<ScanProfile>(`/scan-profiles/${id}`);
  },

  create: async (data: ScanProfileCreate): Promise<ScanProfile> => {
    return fetchApi<ScanProfile>('/scan-profiles/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  delete: async (id: string): Promise<void> => {
    return fetchApi<void>(`/scan-profiles/${id}`, {
      method: 'DELETE',
    });
  }
};
