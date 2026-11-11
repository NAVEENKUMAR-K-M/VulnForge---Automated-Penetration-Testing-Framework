import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderKanban, Plus, ArrowRight } from 'lucide-react';
import { Button } from '../components/common/Button';
import { PageHeader, EmptyState, Loading, ErrorBanner, Modal, Field, Input, Textarea } from '../components/ui';
import { Stagger, StaggerItem, motion } from '../components/motion';
import { workspacesApi } from '../api/workspaces';
import type { Workspace } from '../api/workspaces';

export const Workspaces: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    workspacesApi
      .list()
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const create = async () => {
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const ws = await workspacesApi.create({ name, description: description || undefined });
      setOpen(false);
      setName('');
      setDescription('');
      navigate(`/projects/${ws.id}/dashboard`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Engagements"
        title="Workspaces"
        subtitle="Each workspace is an isolated engagement — its own targets, scope, scans, and findings."
        actions={
          <Button variant="primary" leftIcon={<Plus className="w-4 h-4" />} onClick={() => setOpen(true)}>
            New workspace
          </Button>
        }
      />

      <ErrorBanner message={error} />

      {loading ? (
        <Loading label="Loading workspaces…" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<FolderKanban className="w-12 h-12" />}
          title="No workspaces yet"
          hint="Create your first workspace to start scoping targets and running assessments."
          action={<Button variant="primary" leftIcon={<Plus className="w-4 h-4" />} onClick={() => setOpen(true)}>New workspace</Button>}
        />
      ) : (
        <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((w) => (
            <StaggerItem key={w.id}>
              <motion.button
                onClick={() => navigate(`/projects/${w.id}/dashboard`)}
                whileHover={{ y: -4 }}
                transition={{ type: 'spring', stiffness: 300, damping: 22 }}
                className="w-full text-left panel panel-interactive p-5 group"
              >
                <div className="flex items-start justify-between">
                  <div className="w-10 h-10 rounded-xl bg-primary/15 border border-primary/25 flex items-center justify-center">
                    <FolderKanban className="w-5 h-5 text-primary" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                </div>
                <h3 className="mt-4 font-display font-semibold text-text-primary">{w.name}</h3>
                <p className="text-sm text-text-secondary mt-1 line-clamp-2">{w.description || 'No description'}</p>
                <p className="data text-xs text-text-muted mt-3">Created {new Date(w.created_at).toLocaleDateString()}</p>
              </motion.button>
            </StaggerItem>
          ))}
        </Stagger>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="New workspace"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={create} isLoading={saving} disabled={!name.trim()}>
              Create workspace
            </Button>
          </>
        }
      >
        <Field label="Name">
          <Input placeholder="Acme Corp — External Assessment" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label="Description" hint="Optional — scope, client, or engagement notes.">
          <Textarea placeholder="What is this engagement about?" value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
      </Modal>
    </div>
  );
};
