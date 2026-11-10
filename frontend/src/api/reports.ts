import { fetchApi, BASE_URL } from './client';

export interface ReportVuln {
  title: string;
  severity: string;
  cve_id: string | null;
  host: string | null;
}

export interface ReportJson {
  workspace: string;
  date: string;
  executive_summary: string;
  stats: {
    total_assets: number;
    total_vulnerabilities: number;
    critical_high_findings: number;
  };
  vulnerabilities: ReportVuln[];
}

export type ReportFormat = 'json' | 'markdown' | 'html' | 'pdf';

export const reportsApi = {
  getJson: (workspaceId: string): Promise<ReportJson> =>
    fetchApi<ReportJson>(`/workspaces/${workspaceId}/reports/generate?format=json`, { method: 'POST' }),

  /** Fetch a report in the given format and trigger a browser download. */
  download: async (workspaceId: string, format: ReportFormat): Promise<void> => {
    const token = localStorage.getItem('token');
    const res = await fetch(
      `${BASE_URL}/workspaces/${workspaceId}/reports/generate?format=${format}`,
      { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {} }
    );
    if (!res.ok) throw new Error(`Report generation failed (${res.status})`);
    const blob = await res.blob();
    const ext = format === 'markdown' ? 'md' : format;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vulnforge-report.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
