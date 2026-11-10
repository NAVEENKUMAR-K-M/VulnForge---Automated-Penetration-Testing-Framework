import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Radar, Play, Square } from 'lucide-react';
import { Button } from '../../components/common/Button';
import {
  PageHeader, EmptyState, Loading, ErrorBanner, DataTable, StatusBadge, Modal, Field, Input, Select,
} from '../../components/ui';
import type { Column } from '../../components/ui';
import { scansApi } from '../../api/scans';
import type { Scan } from '../../api/scans';
import { targetsApi } from '../../api/targets';
import type { Target } from '../../api/targets';

const SCAN_TYPES = [
  { v: 'reconnaissance', label: 'Reconnaissance (passive)' },
  { v: 'vulnerability', label: 'Vulnerability scan' },
  { v: 'full', label: 'Full (recon + vuln)' },
];

export const ProjectScans: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<Scan[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', target_id: '', scan_type: 'reconnaissance' });

  const load = useCallback(() => {
    if (!id) return;
    scansApi.list(id).then(setRows).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    load();
    if (id) targetsApi.list(id).then(setTargets).catch(() => {});
  }, [id, load]);

  // Poll while any scan is active.
  useEffect(() => {
    if (!rows.some((s) => s.status === 'running' || s.status === 'pending')) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [rows, load]);

  const create = async () => {
    if (!id || !form.name.trim() || !form.target_id) return;
    setSaving(true);
    setError(null);
    try {
      await scansApi.create(id, form as any);
      setOpen(false);
      setForm({ name: '', target_id: '', scan_type: 'reconnaissance' });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const cancel = async (s: Scan) => {
    if (!id) return;
    try { await scansApi.cancel(id, s.id); load(); } catch (e: any) { setError(e.message); }
  };

  const cols: Column<Scan>[] = [
    { header: 'Scan', cell: (s) => <span className="text-text-primary font-medium">{s.name}</span> },
    { header: 'Type', cell: (s) => <span className="data text-xs">{s.scan_type}</span> },
    { header: 'Status', cell: (s) => <StatusBadge status={s.status} /> },
    { header: 'Started', cell: (s) => <span className="data text-xs text-text-muted">{s.started_at ? new Date(s.started_at).toLocaleString() : '—'}</span> },
    {
      header: '',
      width: '80px',
      cell: (s) =>
        s.status === 'running' || s.status === 'pending' ? (
          <Button size="sm" variant="danger" leftIcon={<Square className="w-3 h-3" />} onClick={() => cancel(s)}>Cancel</Button>
        ) : null,
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Assessment"
        title="Scans"
        subtitle="Run tool-driven scans against in-scope targets. Results feed Assets and Vulnerabilities."
        actions={<Button variant="primary" leftIcon={<Play className="w-4 h-4" />} onClick={() => setOpen(true)} disabled={targets.length === 0}>New scan</Button>}
      />
      <ErrorBanner message={error} />

      {loading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Radar className="w-12 h-12" />}
          title="No scans yet"
          hint={targets.length === 0 ? 'Add a target first, then run a scan against it.' : 'Start a scan to discover assets and vulnerabilities.'}
          action={targets.length > 0 ? <Button variant="primary" leftIcon={<Play className="w-4 h-4" />} onClick={() => setOpen(true)}>New scan</Button> : undefined}
        />
      ) : (
        <DataTable columns={cols} rows={rows} keyFn={(s) => s.id} />
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="New scan"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={create} isLoading={saving} disabled={!form.name.trim() || !form.target_id}>Start scan</Button>
          </>
        }
      >
        <Field label="Name"><Input placeholder="External recon — Q1" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus /></Field>
        <Field label="Target">
          <Select value={form.target_id} onChange={(e) => setForm({ ...form, target_id: e.target.value })}>
            <option value="">Select a target…</option>
            {targets.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.value})</option>)}
          </Select>
        </Field>
        <Field label="Scan type">
          <Select value={form.scan_type} onChange={(e) => setForm({ ...form, scan_type: e.target.value })}>
            {SCAN_TYPES.map((t) => <option key={t.v} value={t.v}>{t.label}</option>)}
          </Select>
        </Field>
      </Modal>
    </div>
  );
};
