import { fetchApi } from './client';

export interface ReconAsset {
  id: string;
  workspace_id: string;
  asset_value: string;
  asset_type: string;
  source_tool: string;
  first_seen: string;
  last_seen: string;
  metadata: Record<string, any>;
}

export const assetsApi = {
  list: async (workspaceId: string, skip = 0, limit = 100): Promise<ReconAsset[]> => {
    const res = await fetchApi<{ items: ReconAsset[] }>(`/workspaces/${workspaceId}/assets/?skip=${skip}&limit=${limit}`);
    return res.items;
  },
};
