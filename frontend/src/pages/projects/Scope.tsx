import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Plus, Trash2, ShieldAlert } from 'lucide-react';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  PageHeader, EmptyState, Loading, ErrorBanner, DataTable, Modal, Field, Input, Select, Textarea,
} from '../../components/ui';
import type { Column } from '../../components/ui';
import { scopeApi } from '../../api/scope';
import type { ScopeRule } from '../../api/scope';

const RULE_TYPES = ['domain', 'subdomain', 'host', 'cidr', 'wildcard'];

export const ProjectScope: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<ScopeRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<{ rule_type: string; value: string; disposition: 'allow' | 'exclude'; description: string }>({
    rule_type: 'domain', value: '', disposition: 'allow', description: '',
  });

  const load = () => {
    if (!id) return;
    setLoading(true);
    scopeApi
      .list(id)
      .then((d: any) => setRows(Array.isArray(d) ? d : d.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, [id]);

  const create = async () => {
    if (!id || !form.value.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await scopeApi.create(id, { ...form, description: form.description || undefined });
      setOpen(false);
      setForm({ rule_type: 'domain', value: '', disposition: 'allow', description: '' });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (r: ScopeRule) => {
    if (!id || !confirm(`Delete scope rule "${r.value}"?`)) return;
    try { await scopeApi.delete(id, r.id); load(); } catch (e: any) { setError(e.message); }
  };

  const cols: Column<ScopeRule>[] = [
    {
      header: 'Disposition',
      cell: (r) => <Badge variant={r.disposition === 'allow' ? 'success' : 'danger'}>{r.disposition === 'allow' ? 'In scope' : 'Excluded'}</Badge>,
    },
    { header: 'Type', cell: (r) => <Badge variant="secondary">{r.rule_type}</Badge> },
    { header: 'Value', cell: (r) => <span className="data">{r.value}</span> },
    { header: 'Notes', cell: (r) => <span className="text-text-secondary text-sm">{r.description || '—'}</span> },
    {
      header: '',
      width: '48px',
      cell: (r) => (
        <button onClick={() => remove(r)} className="text-text-muted hover:text-danger" title="Delete">
          <Trash2 className="w-4 h-4" />
        </button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Authorization"
        title="Scope"
        subtitle="Default-deny: scans and the agent only run against targets an ALLOW rule covers. EXCLUDE rules always win."
        actions={<Button variant="primary" leftIcon={<Plus className="w-4 h-4" />} onClick={() => setOpen(true)}>Add rule</Button>}
      />
      <ErrorBanner message={error} />

      {loading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<ShieldAlert className="w-12 h-12" />}
          title="No scope defined"
          hint="Scanning is blocked until you add at least one ALLOW rule. This keeps every assessment inside what you're authorized to test."
          action={<Button variant="primary" leftIcon={<Plus className="w-4 h-4" />} onClick={() => setOpen(true)}>Add rule</Button>}
        />
      ) : (
        <DataTable columns={cols} rows={rows} keyFn={(r) => r.id} />
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Add scope rule"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={create} isLoading={saving} disabled={!form.value.trim()}>Add rule</Button>
          </>
        }
      >
        <Field label="Disposition">
          <Select value={form.disposition} onChange={(e) => setForm({ ...form, disposition: e.target.value as any })}>
            <option value="allow">Allow (in scope)</option>
            <option value="exclude">Exclude (never scan)</option>
          </Select>
        </Field>
        <Field label="Type">
          <Select value={form.rule_type} onChange={(e) => setForm({ ...form, rule_type: e.target.value })}>
            {RULE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
        </Field>
        <Field label="Value" hint="e.g. example.com, *.example.com, 10.0.0.0/24, 192.168.1.10">
          <Input placeholder="example.com" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} autoFocus />
        </Field>
        <Field label="Notes"><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
      </Modal>
    </div>
  );
};
