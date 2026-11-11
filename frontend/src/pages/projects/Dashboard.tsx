import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Crosshair, Server, Bug, Radar, ArrowRight, ShieldAlert } from 'lucide-react';
import { PageHeader, StatCard, Loading, DataTable, StatusBadge } from '../../components/ui';
import type { Column } from '../../components/ui';
import { Donut, Stagger, StaggerItem } from '../../components/motion';
import type { DonutSeg } from '../../components/motion';
import { scansApi } from '../../api/scans';
import type { Scan } from '../../api/scans';
import { assetsApi } from '../../api/assets';
import { targetsApi } from '../../api/targets';
import { reportsApi } from '../../api/reports';
import type { ReportVuln } from '../../api/reports';

const SEV_COLOR: Record<string, string> = {
  critical: '#F43F5E', high: '#FB7A3C', medium: '#FBBF24', low: '#38BDF8', info: '#8792A6',
};

export const ProjectDashboard: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [scans, setScans] = useState<Scan[]>([]);
  const [vulns, setVulns] = useState<ReportVuln[]>([]);
  const [counts, setCounts] = useState({ targets: 0, assets: 0 });

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.allSettled([scansApi.list(id), assetsApi.list(id), targetsApi.list(id), reportsApi.getJson(id)]).then(
      ([s, a, t, r]) => {
        if (s.status === 'fulfilled') setScans(s.value);
        if (r.status === 'fulfilled') setVulns(r.value.vulnerabilities);
        setCounts({
          targets: t.status === 'fulfilled' ? t.value.length : 0,
          assets: a.status === 'fulfilled' ? a.value.length : 0,
        });
        setLoading(false);
      }
    );
  }, [id]);

  const sev = useMemo(() => {
    const c: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    vulns.forEach((v) => { c[v.severity] = (c[v.severity] || 0) + 1; });
    return c;
  }, [vulns]);

  const segments: DonutSeg[] = (['critical', 'high', 'medium', 'low', 'info'] as const)
    .filter((k) => sev[k] > 0)
    .map((k) => ({ value: sev[k], color: SEV_COLOR[k], label: k }));

  const critHigh = sev.critical + sev.high;

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

      <div className="grid gap-5 lg:grid-cols-3 mb-5">
        {/* Severity donut */}
        <div className="panel p-6 flex flex-col items-center justify-center">
          <p className="text-xs uppercase tracking-wider text-text-muted self-start mb-2">Findings by severity</p>
          {vulns.length ? (
            <>
              <Donut segments={segments} centerLabel="findings" />
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-4">
                {(['critical', 'high', 'medium', 'low', 'info'] as const).filter((k) => sev[k] > 0).map((k) => (
                  <span key={k} className="flex items-center gap-1.5 text-xs text-text-secondary capitalize">
                    <span className="w-2 h-2 rounded-full" style={{ background: SEV_COLOR[k] }} /> {k} · {sev[k]}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-10 text-text-muted">
              <ShieldAlert className="w-10 h-10 mb-2 opacity-30" />
              <p className="text-sm">No findings yet</p>
            </div>
          )}
        </div>

        {/* Stat grid */}
        <Stagger className="lg:col-span-2 grid gap-4 sm:grid-cols-2">
          <StaggerItem><StatCard label="Targets" value={counts.targets} icon={<Crosshair className="w-5 h-5" />} /></StaggerItem>
          <StaggerItem><StatCard label="Assets discovered" value={counts.assets} icon={<Server className="w-5 h-5" />} /></StaggerItem>
          <StaggerItem><StatCard label="Vulnerabilities" value={vulns.length} icon={<Bug className="w-5 h-5" />} tone="primary" /></StaggerItem>
          <StaggerItem><StatCard label="Critical / High" value={critHigh} tone={critHigh ? 'danger' : 'default'} /></StaggerItem>
        </Stagger>
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm uppercase tracking-wider text-text-muted">Recent scans</h2>
        <Link to={`/projects/${id}/scans`} className="text-sm text-primary inline-flex items-center gap-1">All scans <ArrowRight className="w-3.5 h-3.5" /></Link>
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
