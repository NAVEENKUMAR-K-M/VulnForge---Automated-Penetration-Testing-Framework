import { fetchApi } from './client';

export interface Workspace {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  created_by_id: string;
}

export interface WorkspaceCreate {
  name: string;
  description?: string;
}

export interface WorkspaceUpdate {
  name?: string;
  description?: string;
}

export const workspacesApi = {
  list: async (skip = 0, limit = 100): Promise<Workspace[]> => {
    const res = await fetchApi<{ items: Workspace[] }>(`/workspaces/?skip=${skip}&limit=${limit}`);
    return res.items;
  },

  get: async (id: string): Promise<Workspace> => {
    return fetchApi<Workspace>(`/workspaces/${id}`);
  },

  create: async (data: WorkspaceCreate): Promise<Workspace> => {
    return fetchApi<Workspace>('/workspaces/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  update: async (id: string, data: WorkspaceUpdate): Promise<Workspace> => {
    return fetchApi<Workspace>(`/workspaces/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: async (id: string): Promise<void> => {
    return fetchApi<void>(`/workspaces/${id}`, {
      method: 'DELETE',
    });
  }
};
