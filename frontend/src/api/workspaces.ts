import { fetchApi } from './client';
import type { UserResponse } from './auth';

export interface Workspace {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  created_by_id: string;
  is_active?: boolean;
}

export interface WorkspaceCreate {
  name: string;
  description?: string;
}

export interface WorkspaceUpdate {
  name?: string;
  description?: string;
}

export interface WorkspaceMember {
  user_id: string;
  role: string;
  user?: UserResponse;
}

export interface WorkspaceDashboard {
  targets_count: number;
  open_vulnerabilities_count: number;
  recent_scans: any[];
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
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  delete: async (id: string): Promise<void> => {
    return fetchApi<void>(`/workspaces/${id}`, {
      method: 'DELETE',
    });
  },

  restore: async (id: string): Promise<Workspace> => {
    return fetchApi<Workspace>(`/workspaces/${id}/restore`, {
      method: 'POST',
    });
  },

  getDashboard: async (id: string): Promise<WorkspaceDashboard> => {
    return fetchApi<WorkspaceDashboard>(`/workspaces/${id}/dashboard`);
  },

  listMembers: async (id: string): Promise<WorkspaceMember[]> => {
    return fetchApi<WorkspaceMember[]>(`/workspaces/${id}/members`);
  },

  addMember: async (id: string, userId: string, role: string = 'viewer'): Promise<WorkspaceMember> => {
    return fetchApi<WorkspaceMember>(`/workspaces/${id}/members`, {
      method: 'POST',
      body: JSON.stringify({ target_user_id: userId, role }),
    });
  },

  updateMember: async (id: string, userId: string, role: string): Promise<WorkspaceMember> => {
    return fetchApi<WorkspaceMember>(`/workspaces/${id}/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    });
  },

  removeMember: async (id: string, userId: string): Promise<void> => {
    return fetchApi<void>(`/workspaces/${id}/members/${userId}`, {
      method: 'DELETE',
    });
  }
};
