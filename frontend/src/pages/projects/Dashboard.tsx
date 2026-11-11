import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Crosshair, Server, Bug, Radar, ArrowRight, Activity, ShieldAlert } from 'lucide-react';
import { PageHeader, StatCard, Loading, DataTable, StatusBadge, Spinner } from '../../components/ui';
import type { Column } from '../../components/ui';
import { Stagger, StaggerItem } from '../../components/motion';
import { ActivityArea, SeverityBars } from '../../components/charts';
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
  const [vulnsLoading, setVulnsLoading] = useState(true);
  const [counts, setCounts] = useState({ targets: 0, assets: 0 });

  useEffect(() => {
    if (!id) return;
    // Fast data renders the page immediately.
    setLoading(true);
    Promise.allSettled([scansApi.list(id), assetsApi.list(id), targetsApi.list(id)]).then(([s, a, t]) => {
      if (s.status === 'fulfilled') setScans(s.value);
      setCounts({
        targets: t.status === 'fulfilled' ? t.value.length : 0,
        assets: a.status === 'fulfilled' ? a.value.length : 0,
      });
      setLoading(false);
    });
    // Findings come from report generation (slower) — load without blocking the page.
    setVulnsLoading(true);
    reportsApi.getJson(id).then((r) => setVulns(r.vulnerabilities)).catch(() => {}).finally(() => setVulnsLoading(false));
  }, [id]);

  const sev = useMemo(() => {
    const c: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    vulns.forEach((v) => { c[v.severity] = (c[v.severity] || 0) + 1; });
    return c;
  }, [vulns]);

  const sevData = (['critical', 'high', 'medium', 'low', 'info'] as const).map((k) => ({
    name: k[0].toUpperCase() + k.slice(1), value: sev[k], color: SEV_COLOR[k],
  }));

  const activity = useMemo(() => {
    const days: { key: string; label: string; value: number }[] = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      days.push({ key: d.toISOString().slice(0, 10), label: d.toLocaleDateString(undefined, { weekday: 'short' }), value: 0 });
    }
    const map = Object.fromEntries(days.map((d) => [d.key, d]));
    scans.forEach((s) => { const k = (s.created_at || '').slice(0, 10); if (map[k]) map[k].value++; });
    return days;
  }, [scans]);

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
      <PageHeader eyebrow="Overview" title="Workspace overview" subtitle="Live snapshot of this engagement's attack surface and findings." />

      <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-5">
        <StaggerItem><StatCard label="Targets" value={counts.targets} icon={<Crosshair className="w-5 h-5" />} /></StaggerItem>
        <StaggerItem><StatCard label="Assets discovered" value={counts.assets} icon={<Server className="w-5 h-5" />} /></StaggerItem>
        <StaggerItem><StatCard label="Vulnerabilities" value={vulns.length} icon={<Bug className="w-5 h-5" />} tone="primary" /></StaggerItem>
        <StaggerItem><StatCard label="Critical / High" value={critHigh} tone={critHigh ? 'danger' : 'default'} /></StaggerItem>
      </Stagger>

      <div className="grid gap-5 lg:grid-cols-5 mb-5">
        <div className="panel p-5 lg:col-span-3">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4 text-primary" />
            <h2 className="font-display font-semibold text-text-primary">Scan activity</h2>
            <span className="text-xs text-text-muted ml-auto">last 7 days</span>
          </div>
          <ActivityArea data={activity} />
        </div>
        <div className="panel p-5 lg:col-span-2">
          <h2 className="font-display font-semibold text-text-primary mb-1">Findings by severity</h2>
          {vulnsLoading ? (
            <div className="flex justify-center items-center py-16"><Spinner /></div>
          ) : vulns.length ? (
            <SeverityBars data={sevData.filter((d) => d.value > 0)} />
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-text-muted">
              <ShieldAlert className="w-10 h-10 mb-2 opacity-30" />
              <p className="text-sm">No findings yet</p>
            </div>
          )}
        </div>
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
