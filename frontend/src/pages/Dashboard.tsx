import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FolderKanban, Crosshair, Radar, Bug, Activity, ArrowRight, ShieldAlert, Command,
} from 'lucide-react';
import { StatCard, Loading, Spinner, DataTable, StatusBadge } from '../components/ui';
import type { Column } from '../components/ui';
import { Stagger, StaggerItem, motion } from '../components/motion';
import { ActivityArea, SeverityBars } from '../components/charts';
import { openCommandPalette } from '../components/CommandPalette';
import { useAuth } from '../context/AuthContext';
import { workspacesApi } from '../api/workspaces';
import type { Workspace } from '../api/workspaces';
import { scansApi } from '../api/scans';
import type { Scan } from '../api/scans';
import { targetsApi } from '../api/targets';
import { reportsApi } from '../api/reports';

const SEV_COLOR: Record<string, string> = {
  critical: '#E11D48', high: '#EA580C', medium: '#CA8A04', low: '#0284C7', info: '#64748B',
};
type ScanRow = Scan & { wsName: string };

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [scans, setScans] = useState<ScanRow[]>([]);
  const [totals, setTotals] = useState({ targets: 0 });
  const [sev, setSev] = useState<Record<string, number>>({ critical: 0, high: 0, medium: 0, low: 0, info: 0 });
  const [wsFindings, setWsFindings] = useState<Record<string, number>>({});
  const [sevLoading, setSevLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      let ws: Workspace[] = [];
      try { ws = await workspacesApi.list(); } catch { /* ignore */ }
      setWorkspaces(ws);

      const results = await Promise.allSettled(
        ws.map((w) => Promise.all([scansApi.list(w.id).catch(() => []), targetsApi.list(w.id).catch(() => [])]))
      );
      const allScans: ScanRow[] = [];
      let targets = 0;
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          const [sc, tg] = r.value;
          targets += tg.length;
          allScans.push(...sc.map((s) => ({ ...s, wsName: ws[i].name })));
        }
      });
      allScans.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
      setScans(allScans);
      setTotals({ targets });
      setLoading(false);

      // Findings aggregation (slower — report generation) streams in.
      setSevLoading(true);
      const capped = ws.slice(0, 6);
      const reps = await Promise.allSettled(capped.map((w) => reportsApi.getJson(w.id)));
      const c: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
      const perWs: Record<string, number> = {};
      reps.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          perWs[capped[i].id] = r.value.vulnerabilities.length;
          r.value.vulnerabilities.forEach((v) => { c[v.severity] = (c[v.severity] || 0) + 1; });
        }
      });
      setSev(c);
      setWsFindings(perWs);
      setSevLoading(false);
    })();
  }, []);

  const activity = useMemo(() => {
    const days: { key: string; label: string; value: number }[] = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      days.push({ key: d.toISOString().slice(0, 10), label: d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }), value: 0 });
    }
    const map = Object.fromEntries(days.map((d) => [d.key, d]));
    scans.forEach((s) => { const k = (s.created_at || '').slice(0, 10); if (map[k]) map[k].value++; });
    return days;
  }, [scans]);

  const totalFindings = Object.values(sev).reduce((a, b) => a + b, 0);
  const critHigh = sev.critical + sev.high;
  const sevData = (['critical', 'high', 'medium', 'low', 'info'] as const).map((k) => ({ name: k[0].toUpperCase() + k.slice(1), value: sev[k], color: SEV_COLOR[k] }));
  const firstName = (user?.full_name || user?.email || 'Operator').split(/[\s@]/)[0];

  const cols: Column<ScanRow>[] = [
    { header: 'Scan', cell: (s) => <span className="text-text-primary font-medium">{s.name}</span> },
    { header: 'Workspace', cell: (s) => <span className="text-sm text-text-secondary">{s.wsName}</span> },
    { header: 'Status', cell: (s) => <StatusBadge status={s.status} /> },
    { header: 'When', cell: (s) => <span className="data text-xs text-text-muted">{s.created_at ? new Date(s.created_at).toLocaleString() : '—'}</span> },
  ];

  if (loading) return <Loading label="Loading your operations…" />;

  return (
    <div>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-7">
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <span className="h-3 w-[3px] rounded-full bg-primary" />
            <span className="data text-xs uppercase tracking-[0.2em] text-primary/90">Operations console</span>
          </div>
          <h1 className="font-display font-semibold text-text-primary tracking-tight" style={{ fontSize: 'clamp(1.7rem, 1.2rem + 1.8vw, 2.4rem)' }}>
            Welcome back, {firstName}
          </h1>
          <p className="text-text-secondary mt-1.5">Live overview across all your engagements.</p>
        </div>
        <button onClick={openCommandPalette} className="flex items-center gap-2 h-9 px-3 rounded-lg border border-border-color bg-surface/60 text-text-secondary hover:border-primary/40 transition-colors">
          <Command className="w-4 h-4" /> Quick actions <kbd className="data text-[0.65rem] border border-border-color rounded px-1.5 py-0.5">⌘K</kbd>
        </button>
      </div>

      <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-5">
        <StaggerItem><StatCard label="Workspaces" value={workspaces.length} icon={<FolderKanban className="w-5 h-5" />} tone="primary" /></StaggerItem>
        <StaggerItem><StatCard label="Targets" value={totals.targets} icon={<Crosshair className="w-5 h-5" />} /></StaggerItem>
        <StaggerItem><StatCard label="Scans run" value={scans.length} icon={<Radar className="w-5 h-5" />} /></StaggerItem>
        <StaggerItem><StatCard label="Findings" value={totalFindings} icon={<Bug className="w-5 h-5" />} tone={critHigh ? 'danger' : 'default'} /></StaggerItem>
      </Stagger>

      <div className="grid gap-5 lg:grid-cols-5 mb-5">
        <div className="panel p-5 lg:col-span-3">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4 text-primary" />
            <h2 className="font-display font-semibold text-text-primary">Scan activity</h2>
            <span className="text-xs text-text-muted ml-auto">all workspaces · 14 days</span>
          </div>
          <ActivityArea data={activity} height={230} />
        </div>
        <div className="panel p-5 lg:col-span-2">
          <h2 className="font-display font-semibold text-text-primary mb-1">Findings by severity</h2>
          {sevLoading ? (
            <div className="flex justify-center items-center py-16"><Spinner /></div>
          ) : totalFindings ? (
            <SeverityBars data={sevData.filter((d) => d.value > 0)} />
          ) : (
            <div className="flex flex-col items-center justify-center py-14 text-text-muted">
              <ShieldAlert className="w-10 h-10 mb-2 opacity-30" />
              <p className="text-sm">No findings yet</p>
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h2 className="text-sm uppercase tracking-wider text-text-muted mb-3">Recent activity</h2>
          {scans.length ? (
            <DataTable columns={cols} rows={scans.slice(0, 7)} keyFn={(s) => s.id} />
          ) : (
            <div className="panel p-8 text-center text-text-secondary">
              <Radar className="w-10 h-10 mx-auto mb-3 opacity-30" /> No scans across your workspaces yet.
            </div>
          )}
        </div>
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm uppercase tracking-wider text-text-muted">Engagements</h2>
            <Link to="/workspaces" className="text-sm text-primary inline-flex items-center gap-1">All <ArrowRight className="w-3.5 h-3.5" /></Link>
          </div>
          <div className="space-y-3">
            {workspaces.length === 0 && <p className="text-sm text-text-muted">No workspaces yet.</p>}
            {workspaces.map((w) => {
              const scanCount = scans.filter((s) => s.workspace_id === w.id).length;
              const f = wsFindings[w.id];
              return (
                <motion.div key={w.id} whileHover={{ x: 3 }} transition={{ type: 'spring', stiffness: 300, damping: 22 }}>
                  <Link to={`/projects/${w.id}/dashboard`} className="panel panel-interactive p-4 flex items-center gap-3 group">
                    <span className="w-9 h-9 rounded-lg bg-primary/12 border border-primary/20 flex items-center justify-center">
                      <FolderKanban className="w-4 h-4 text-primary" />
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-text-primary truncate">{w.name}</p>
                      <p className="text-xs text-text-muted">{scanCount} scan{scanCount === 1 ? '' : 's'} · {sevLoading ? '…' : (f ?? 0)} finding{f === 1 ? '' : 's'}</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-primary transition-colors" />
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
