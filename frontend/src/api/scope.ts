import { fetchApi } from './client';

export interface ScopeRule {
  id: string;
  workspace_id: string;
  rule_type: string;
  value: string;
  disposition: 'allow' | 'exclude';
  description: string | null;
  created_at: string;
}

export interface ScopeRuleCreate {
  rule_type: string;
  value: string;
  disposition: 'allow' | 'exclude';
  description?: string;
}

export const scopeApi = {
  list: async (workspaceId: string): Promise<ScopeRule[]> => {
    return fetchApi<ScopeRule[]>(`/workspaces/${workspaceId}/scope/rules`);
  },

  create: async (workspaceId: string, data: ScopeRuleCreate): Promise<ScopeRule> => {
    return fetchApi<ScopeRule>(`/workspaces/${workspaceId}/scope/rules`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  delete: async (workspaceId: string, ruleId: string): Promise<void> => {
    return fetchApi<void>(`/workspaces/${workspaceId}/scope/rules/${ruleId}`, {
      method: 'DELETE',
    });
  }
};
