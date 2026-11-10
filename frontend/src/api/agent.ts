import { fetchApi } from './client';

export type AgentRunStatus =
  | 'pending'
  | 'running'
  | 'awaiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type ActionTier = 'passive' | 'active';
export type AgentActionState =
  | 'proposed'
  | 'approved'
  | 'rejected'
  | 'executed'
  | 'failed'
  | 'skipped';

export interface AgentAction {
  id: string;
  run_id: string;
  step_index: number;
  tool_name: string;
  target_value: string;
  tier: ActionTier;
  state: AgentActionState;
  params: Record<string, any>;
  rationale: string | null;
  scope_verdict: string | null;
  result_summary: string | null;
  error_message: string | null;
  created_at: string;
}

export interface AgentRunSummary {
  id: string;
  name: string;
  status: AgentRunStatus;
  target_id: string;
  workspace_id: string;
  created_at: string;
}

export interface AgentRunDetail extends AgentRunSummary {
  objective: string | null;
  scan_id: string | null;
  error_message: string | null;
  actions: AgentAction[];
}

export interface AgentRunCreate {
  target_id: string;
  name?: string;
  objective?: string;
}

export const agentApi = {
  listRuns: async (workspaceId: string, page = 1, pageSize = 50): Promise<AgentRunSummary[]> => {
    const res = await fetchApi<{ items: AgentRunSummary[] }>(
      `/workspaces/${workspaceId}/agent/runs?page=${page}&page_size=${pageSize}`
    );
    return res.items;
  },

  getRun: (workspaceId: string, runId: string): Promise<AgentRunDetail> =>
    fetchApi<AgentRunDetail>(`/workspaces/${workspaceId}/agent/runs/${runId}`),

  startRun: (workspaceId: string, data: AgentRunCreate): Promise<AgentRunDetail> =>
    fetchApi<AgentRunDetail>(`/workspaces/${workspaceId}/agent/runs`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  pending: (workspaceId: string, runId: string): Promise<AgentAction[]> =>
    fetchApi<AgentAction[]>(`/workspaces/${workspaceId}/agent/runs/${runId}/pending`),

  approve: (workspaceId: string, runId: string, actionId: string): Promise<AgentRunDetail> =>
    fetchApi<AgentRunDetail>(
      `/workspaces/${workspaceId}/agent/runs/${runId}/actions/${actionId}/approve`,
      { method: 'POST' }
    ),

  reject: (workspaceId: string, runId: string, actionId: string): Promise<AgentRunDetail> =>
    fetchApi<AgentRunDetail>(
      `/workspaces/${workspaceId}/agent/runs/${runId}/actions/${actionId}/reject`,
      { method: 'POST' }
    ),
};
