import { fetchApi } from './client';

export type ScanStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
export type ScanType = 'reconnaissance' | 'vulnerability' | 'exploitation' | 'full';

export interface Scan {
  id: string;
  name: string;
  description: string | null;
  status: ScanStatus;
  target_id: string;
  workspace_id: string | null;
  scan_type: ScanType;
  priority: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  celery_task_id: string | null;
  created_at: string;
}

export interface ScanCreate {
  name: string;
  target_id: string;
  scan_type: ScanType;
  profile_id?: string;
  priority?: string;
  description?: string;
}

export const scansApi = {
  list: async (workspaceId: string, page = 1, pageSize = 50): Promise<Scan[]> => {
    const res = await fetchApi<{ items: Scan[] }>(
      `/workspaces/${workspaceId}/scans?page=${page}&page_size=${pageSize}`
    );
    return res.items;
  },

  get: (workspaceId: string, scanId: string): Promise<Scan> =>
    fetchApi<Scan>(`/workspaces/${workspaceId}/scans/${scanId}`),

  create: (workspaceId: string, data: ScanCreate): Promise<Scan> =>
    fetchApi<Scan>(`/workspaces/${workspaceId}/scans`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  cancel: (workspaceId: string, scanId: string): Promise<Scan> =>
    fetchApi<Scan>(`/workspaces/${workspaceId}/scans/${scanId}/cancel`, { method: 'POST' }),
};
