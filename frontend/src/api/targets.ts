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

export const targetsApi = {
  list: async (workspaceId: string, skip = 0, limit = 100): Promise<Target[]> => {
    const res = await fetchApi<{ items: Target[] }>(`/targets/?workspace_id=${workspaceId}&skip=${skip}&limit=${limit}`);
    return res.items;
  },

  create: async (workspaceId: string, data: TargetCreate): Promise<Target> => {
    return fetchApi<Target>(`/targets/`, {
      method: 'POST',
      body: JSON.stringify({ ...data, workspace_id: workspaceId }),
    });
  },

  delete: async (workspaceId: string, targetId: string): Promise<void> => {
    return fetchApi<void>(`/targets/${targetId}`, {
      method: 'DELETE',
    });
  }
};
