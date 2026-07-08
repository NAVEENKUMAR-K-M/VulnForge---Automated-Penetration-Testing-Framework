import { fetchApi } from './client';

export interface ReconAsset {
  id: string;
  workspace_id: string;
  value: string;
  asset_type: string;
  source_tools: string[];
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export const assetsApi = {
  list: async (workspaceId: string, skip = 0, limit = 100): Promise<ReconAsset[]> => {
    const res = await fetchApi<{ items: ReconAsset[] }>(`/workspaces/${workspaceId}/assets/?skip=${skip}&limit=${limit}`);
    return res.items;
  },

  delete: async (workspaceId: string, assetId: string): Promise<void> => {
    return fetchApi<void>(`/workspaces/${workspaceId}/assets/${assetId}`, {
      method: 'DELETE',
    });
  }
};
