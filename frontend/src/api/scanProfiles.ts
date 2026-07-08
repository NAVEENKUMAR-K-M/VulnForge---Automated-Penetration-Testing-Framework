import { fetchApi } from './client';

export interface ScanProfilePlugin {
  plugin_id: string;
  is_enabled: boolean;
  execution_order: number;
  config_override: Record<string, any>;
  plugin_details?: any; // Add specific plugin type if available
}

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

export interface ScanProfileUpdate {
  name?: string;
  description?: string;
  is_default?: boolean;
}

export interface ScanProfileClone {
  name: string;
}

export interface ProfilePluginAdd {
  plugin_id: string;
  is_enabled?: boolean;
  execution_order?: number;
  config_override?: Record<string, any>;
}

export interface ProfilePluginUpdate {
  is_enabled?: boolean;
  execution_order?: number;
  config_override?: Record<string, any>;
}

export const scanProfilesApi = {
  list: async (skip = 0, limit = 100): Promise<ScanProfile[]> => {
    const res = await fetchApi<{ items: ScanProfile[] }>(`/profiles?skip=${skip}&limit=${limit}`);
    return res.items;
  },

  get: async (id: string): Promise<ScanProfile> => {
    return fetchApi<ScanProfile>(`/profiles/${id}`);
  },

  create: async (data: ScanProfileCreate): Promise<ScanProfile> => {
    return fetchApi<ScanProfile>('/profiles', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  update: async (id: string, data: ScanProfileUpdate): Promise<ScanProfile> => {
    return fetchApi<ScanProfile>(`/profiles/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  delete: async (id: string): Promise<void> => {
    return fetchApi<void>(`/profiles/${id}`, {
      method: 'DELETE',
    });
  },

  clone: async (id: string, data: ScanProfileClone): Promise<ScanProfile> => {
    return fetchApi<ScanProfile>(`/profiles/${id}/clone`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  listPlugins: async (id: string): Promise<ScanProfilePlugin[]> => {
    return fetchApi<ScanProfilePlugin[]>(`/profiles/${id}/plugins`);
  },

  addPlugin: async (id: string, data: ProfilePluginAdd): Promise<ScanProfilePlugin> => {
    return fetchApi<ScanProfilePlugin>(`/profiles/${id}/plugins`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updatePlugin: async (id: string, pluginId: string, data: ProfilePluginUpdate): Promise<ScanProfilePlugin> => {
    return fetchApi<ScanProfilePlugin>(`/profiles/${id}/plugins/${pluginId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  removePlugin: async (id: string, pluginId: string): Promise<void> => {
    return fetchApi<void>(`/profiles/${id}/plugins/${pluginId}`, {
      method: 'DELETE',
    });
  }
};
