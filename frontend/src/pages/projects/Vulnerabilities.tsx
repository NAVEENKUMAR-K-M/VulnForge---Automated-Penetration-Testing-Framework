import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Bug, ShieldCheck } from 'lucide-react';
import { PageHeader, StatCard, Loading, ErrorBanner, DataTable, SeverityBadge, EmptyState } from '../../components/ui';
import type { Column } from '../../components/ui';
import { reportsApi } from '../../api/reports';
import type { ReportVuln } from '../../api/reports';

const RANK: Record<string, number> = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };

export const ProjectVulnerabilities: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [vulns, setVulns] = useState<ReportVuln[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    reportsApi
      .getJson(id)
      .then((r) => setVulns([...r.vulnerabilities].sort((a, b) => (RANK[b.severity] || 0) - (RANK[a.severity] || 0))))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const counts = useMemo(() => {
    const c = { critical: 0, high: 0, medium: 0, low: 0, info: 0 } as Record<string, number>;
    vulns.forEach((v) => { c[v.severity] = (c[v.severity] || 0) + 1; });
    return c;
  }, [vulns]);

  const cols: Column<ReportVuln>[] = [
    { header: 'Severity', width: '120px', cell: (v) => <SeverityBadge severity={v.severity} /> },
    { header: 'Finding', cell: (v) => <span className="text-text-primary">{v.title}</span> },
    { header: 'CVE', cell: (v) => (v.cve_id ? <span className="data text-xs">{v.cve_id}</span> : <span className="text-text-muted">—</span>) },
    { header: 'Affected', cell: (v) => (v.host ? <span className="data text-xs">{v.host}</span> : <span className="text-text-muted">—</span>) },
  ];

  if (loading) return <Loading />;

  return (
    <div>
      <PageHeader eyebrow="Findings" title="Vulnerabilities" subtitle="Findings recorded across all scans in this workspace, ranked by severity." />
      <ErrorBanner message={error} />

      <div className="grid gap-3 grid-cols-2 sm:grid-cols-5 mb-6">
        <StatCard label="Critical" value={counts.critical} tone={counts.critical ? 'danger' : 'default'} />
        <StatCard label="High" value={counts.high} tone={counts.high ? 'warning' : 'default'} />
        <StatCard label="Medium" value={counts.medium} />
        <StatCard label="Low" value={counts.low} />
        <StatCard label="Info" value={counts.info} />
      </div>

      {vulns.length === 0 ? (
        <EmptyState icon={<ShieldCheck className="w-12 h-12" />} title="No vulnerabilities recorded" hint="Run a scan or an agent assessment to surface findings." />
      ) : (
        <DataTable columns={cols} rows={vulns} keyFn={(v) => `${v.title}-${v.host}-${v.cve_id}`} />
      )}
      <p className="text-xs text-text-muted mt-3 flex items-center gap-1.5"><Bug className="w-3.5 h-3.5" /> Findings are aggregated from the workspace report.</p>
    </div>
  );
};
