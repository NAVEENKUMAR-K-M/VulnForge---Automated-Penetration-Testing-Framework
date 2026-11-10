import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Crosshair, Server, Bug, Radar, ArrowRight } from 'lucide-react';
import { PageHeader, StatCard, Loading, DataTable, StatusBadge } from '../../components/ui';
import type { Column } from '../../components/ui';
import { scansApi } from '../../api/scans';
import type { Scan } from '../../api/scans';
import { assetsApi } from '../../api/assets';
import { targetsApi } from '../../api/targets';
import { reportsApi } from '../../api/reports';

export const ProjectDashboard: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [scans, setScans] = useState<Scan[]>([]);
  const [counts, setCounts] = useState({ targets: 0, assets: 0, vulns: 0, critHigh: 0 });

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.allSettled([
      scansApi.list(id),
      assetsApi.list(id),
      targetsApi.list(id),
      reportsApi.getJson(id),
    ]).then(([s, a, t, r]) => {
      if (s.status === 'fulfilled') setScans(s.value);
      setCounts({
        targets: t.status === 'fulfilled' ? t.value.length : 0,
        assets: a.status === 'fulfilled' ? a.value.length : 0,
        vulns: r.status === 'fulfilled' ? r.value.stats.total_vulnerabilities : 0,
        critHigh: r.status === 'fulfilled' ? r.value.stats.critical_high_findings : 0,
      });
      setLoading(false);
    });
  }, [id]);

  const cols: Column<Scan>[] = [
    { header: 'Scan', cell: (s) => <span className="text-text-primary font-medium">{s.name}</span> },
    { header: 'Type', cell: (s) => <span className="data text-xs">{s.scan_type}</span> },
    { header: 'Status', cell: (s) => <StatusBadge status={s.status} /> },
    { header: 'Started', cell: (s) => <span className="data text-xs text-text-muted">{s.started_at ? new Date(s.started_at).toLocaleString() : '—'}</span> },
  ];

  if (loading) return <Loading />;

  return (
    <div>
      <PageHeader eyebrow="Overview" title="Workspace overview" subtitle="Snapshot of this engagement's attack surface and findings." />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard label="Targets" value={counts.targets} icon={<Crosshair className="w-5 h-5" />} />
        <StatCard label="Assets discovered" value={counts.assets} icon={<Server className="w-5 h-5" />} />
        <StatCard label="Vulnerabilities" value={counts.vulns} icon={<Bug className="w-5 h-5" />} />
        <StatCard label="Critical / High" value={counts.critHigh} tone={counts.critHigh > 0 ? 'danger' : 'default'} />
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm uppercase tracking-wider text-text-muted">Recent scans</h2>
        <Link to={`/projects/${id}/scans`} className="text-sm text-primary inline-flex items-center gap-1">
          All scans <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
      {scans.length === 0 ? (
        <div className="panel p-8 text-center text-text-secondary">
          <Radar className="w-10 h-10 mx-auto mb-3 opacity-30" />
          No scans yet. Head to <Link to={`/projects/${id}/scans`} className="text-primary">Scans</Link> to run one.
        </div>
      ) : (
        <DataTable columns={cols} rows={scans.slice(0, 6)} keyFn={(s) => s.id} />
      )}
    </div>
  );
};
