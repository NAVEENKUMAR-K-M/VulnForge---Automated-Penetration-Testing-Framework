import { fetchApi } from './client';

export interface Target {
  id: string;
  workspace_id: string | null;
  name: string;
  value: string;
  target_type: string;
  description: string | null;
  scope_notes: string | null;
  tags: string[];
  is_active: boolean;
  created_at: string;
}

export interface TargetCreate {
  name: string;
  value: string;
  target_type: string;
  workspace_id?: string;
  description?: string;
  scope_notes?: string;
  tags?: string[];
}

export interface TargetUpdate {
  name?: string;
  description?: string;
  scope_notes?: string;
}

export const targetsApi = {
  list: async (workspaceId: string, skip = 0, limit = 100): Promise<Target[]> => {
    const res = await fetchApi<{ items: Target[] }>(`/targets/?workspace_id=${workspaceId}&skip=${skip}&limit=${limit}`);
    return res.items;
  },

  get: async (id: string): Promise<Target> => {
    return fetchApi<Target>(`/targets/${id}`);
  },

  create: async (workspaceId: string, data: TargetCreate): Promise<Target> => {
    return fetchApi<Target>(`/targets`, {
      method: 'POST',
      body: JSON.stringify({ ...data, workspace_id: workspaceId }),
    });
  },

  update: async (id: string, data: TargetUpdate): Promise<Target> => {
    return fetchApi<Target>(`/targets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  delete: async (workspaceId: string, targetId: string): Promise<void> => {
    return fetchApi<void>(`/targets/${targetId}`, {
      method: 'DELETE',
    });
  },

  reactivate: async (id: string): Promise<Target> => {
    return fetchApi<Target>(`/targets/${id}/reactivate`, {
      method: 'POST',
    });
  },

  replaceTags: async (id: string, tags: string[]): Promise<Target> => {
    return fetchApi<Target>(`/targets/${id}/tags`, {
      method: 'PUT',
      body: JSON.stringify(tags),
    });
  },

  addTag: async (id: string, tag: string): Promise<Target> => {
    return fetchApi<Target>(`/targets/${id}/tags/${encodeURIComponent(tag)}`, {
      method: 'POST',
    });
  },

  removeTag: async (id: string, tag: string): Promise<Target> => {
    return fetchApi<Target>(`/targets/${id}/tags/${encodeURIComponent(tag)}`, {
      method: 'DELETE',
    });
  }
};
