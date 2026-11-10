import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Crosshair, Plus, Trash2 } from 'lucide-react';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  PageHeader, EmptyState, Loading, ErrorBanner, DataTable, Modal, Field, Input, Select, Textarea,
} from '../../components/ui';
import type { Column } from '../../components/ui';
import { targetsApi } from '../../api/targets';
import type { Target } from '../../api/targets';

const TYPES = [
  { v: 'domain', label: 'Domain' },
  { v: 'host', label: 'Host (IP)' },
  { v: 'network', label: 'Network (CIDR)' },
  { v: 'url', label: 'URL' },
];

export const ProjectTargets: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', value: '', target_type: 'domain', description: '' });

  const load = () => {
    if (!id) return;
    setLoading(true);
    targetsApi.list(id).then(setRows).catch((e) => setError(e.message)).finally(() => setLoading(false));
  };
  useEffect(load, [id]);

  const create = async () => {
    if (!id || !form.name.trim() || !form.value.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await targetsApi.create(id, { ...form, description: form.description || undefined });
      setOpen(false);
      setForm({ name: '', value: '', target_type: 'domain', description: '' });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (t: Target) => {
    if (!id || !confirm(`Delete target "${t.name}"?`)) return;
    try {
      await targetsApi.delete(id, t.id);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const cols: Column<Target>[] = [
    { header: 'Name', cell: (t) => <span className="text-text-primary font-medium">{t.name}</span> },
    { header: 'Value', cell: (t) => <span className="data">{t.value}</span> },
    { header: 'Type', cell: (t) => <Badge variant="secondary">{t.target_type}</Badge> },
    { header: 'Status', cell: (t) => <Badge variant={t.is_active ? 'success' : 'secondary'}>{t.is_active ? 'active' : 'inactive'}</Badge> },
    {
      header: '',
      width: '48px',
      cell: (t) => (
        <button onClick={() => remove(t)} className="text-text-muted hover:text-danger transition-colors" title="Delete">
          <Trash2 className="w-4 h-4" />
        </button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Attack surface"
        title="Targets"
        subtitle="The authorized assets in this engagement. Every scan runs against a target that must be in scope."
        actions={<Button variant="primary" leftIcon={<Plus className="w-4 h-4" />} onClick={() => setOpen(true)}>Add target</Button>}
      />
      <ErrorBanner message={error} />

      {loading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Crosshair className="w-12 h-12" />}
          title="No targets yet"
          hint="Add the hosts, domains, or networks you're authorized to assess."
          action={<Button variant="primary" leftIcon={<Plus className="w-4 h-4" />} onClick={() => setOpen(true)}>Add target</Button>}
        />
      ) : (
        <DataTable columns={cols} rows={rows} keyFn={(t) => t.id} />
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Add target"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={create} isLoading={saving} disabled={!form.name.trim() || !form.value.trim()}>Add target</Button>
          </>
        }
      >
        <Field label="Name"><Input placeholder="Production web" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus /></Field>
        <Field label="Type">
          <Select value={form.target_type} onChange={(e) => setForm({ ...form, target_type: e.target.value })}>
            {TYPES.map((t) => <option key={t.v} value={t.v}>{t.label}</option>)}
          </Select>
        </Field>
        <Field label="Value" hint="e.g. example.com, 10.0.0.0/24, https://app.example.com">
          <Input placeholder="example.com" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
        </Field>
        <Field label="Description"><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
      </Modal>
    </div>
  );
};
