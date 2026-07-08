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

export interface ScopeRuleUpdate {
  rule_type?: string;
  value?: string;
  disposition?: 'allow' | 'exclude';
  description?: string;
}

export interface ScopeOverview {
  allowed_domains: string[];
  excluded_domains: string[];
  allowed_ips: string[];
  excluded_ips: string[];
}

export interface ScopeImportRequest {
  rules: ScopeRuleCreate[];
}

export interface ScopeImportResponse {
  imported_count: number;
}

export interface ScopeCheckResponse {
  is_in_scope: boolean;
  matched_rules: ScopeRule[];
}

export const scopeApi = {
  getOverview: async (workspaceId: string): Promise<ScopeOverview> => {
    return fetchApi<ScopeOverview>(`/workspaces/${workspaceId}/scope`);
  },

  list: async (workspaceId: string): Promise<ScopeRule[]> => {
    return fetchApi<ScopeRule[]>(`/workspaces/${workspaceId}/scope/rules`);
  },

  get: async (workspaceId: string, ruleId: string): Promise<ScopeRule> => {
    return fetchApi<ScopeRule>(`/workspaces/${workspaceId}/scope/rules/${ruleId}`);
  },

  create: async (workspaceId: string, data: ScopeRuleCreate): Promise<ScopeRule> => {
    return fetchApi<ScopeRule>(`/workspaces/${workspaceId}/scope/rules`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  update: async (workspaceId: string, ruleId: string, data: ScopeRuleUpdate): Promise<ScopeRule> => {
    return fetchApi<ScopeRule>(`/workspaces/${workspaceId}/scope/rules/${ruleId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  delete: async (workspaceId: string, ruleId: string): Promise<void> => {
    return fetchApi<void>(`/workspaces/${workspaceId}/scope/rules/${ruleId}`, {
      method: 'DELETE',
    });
  },

  bulkImport: async (workspaceId: string, data: ScopeImportRequest): Promise<ScopeImportResponse> => {
    return fetchApi<ScopeImportResponse>(`/workspaces/${workspaceId}/scope/rules/import`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  checkScope: async (workspaceId: string, targetValue: string, targetType: string): Promise<ScopeCheckResponse> => {
    return fetchApi<ScopeCheckResponse>(`/workspaces/${workspaceId}/scope/check`, {
      method: 'POST',
      body: JSON.stringify({ target_value: targetValue, target_type: targetType }),
    });
  }
};
