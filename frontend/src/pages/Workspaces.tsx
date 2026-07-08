import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardBody } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Plus, Search } from 'lucide-react';
import { workspacesApi } from '../api/workspaces';
import type { Workspace } from '../api/workspaces';

export const Workspaces: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  
  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const fetchWorkspaces = async () => {
    setIsLoading(true);
    try {
      const data = await workspacesApi.list();
      setWorkspaces(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      await workspacesApi.create({ name: newName, description: newDesc });
      setShowModal(false);
      setNewName('');
      setNewDesc('');
      await fetchWorkspaces();
    } catch (err) {
      console.error(err);
      alert('Failed to create workspace');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="flex-col gap-6" style={{ height: '100%', position: 'relative' }}>
      <div className="flex-row items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Workspaces</h1>
          <p className="text-secondary">Manage and isolate your penetration testing engagements.</p>
        </div>
        <Button leftIcon={<Plus size={18} />} onClick={() => setShowModal(true)}>New Workspace</Button>
      </div>

      <Card glass={false} style={{ flex: 1 }}>
        <CardHeader>
          <div className="flex-row items-center gap-4 w-full">
            <div className="flex-row items-center flex-1 gap-2 glass-input" style={{ maxWidth: '300px' }}>
              <Search size={16} className="text-muted" />
              <input 
                type="text" 
                placeholder="Search workspaces..." 
                style={{ background: 'transparent', border: 'none', color: 'inherit', outline: 'none', width: '100%' }}
              />
            </div>
          </div>
        </CardHeader>
        <CardBody>
          {isLoading ? (
            <p className="text-secondary">Loading workspaces...</p>
          ) : workspaces.length === 0 ? (
            <p className="text-secondary">No workspaces found. Create one to get started.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ padding: 'var(--space-3)', color: 'var(--text-muted)' }}>Name</th>
                  <th style={{ padding: 'var(--space-3)', color: 'var(--text-muted)' }}>Created</th>
                  <th style={{ padding: 'var(--space-3)', color: 'var(--text-muted)' }}>Description</th>
                  <th style={{ padding: 'var(--space-3)', color: 'var(--text-muted)' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {workspaces.map(ws => (
                  <tr key={ws.id} style={{ borderBottom: '1px solid var(--border-color)', transition: 'background 0.2s' }} className="hover:bg-surface-hover">
                    <td style={{ padding: 'var(--space-4) var(--space-3)' }}>
                      <NavLink to={`/projects/${ws.id}/dashboard`} style={{ fontWeight: 600 }}>{ws.name}</NavLink>
                    </td>
                    <td style={{ padding: 'var(--space-4) var(--space-3)', color: 'var(--text-secondary)' }}>
                      {new Date(ws.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: 'var(--space-4) var(--space-3)', color: 'var(--text-secondary)' }}>
                      {ws.description || '-'}
                    </td>
                    <td style={{ padding: 'var(--space-4) var(--space-3)' }}>
                      <NavLink to={`/workspaces/${ws.id}`}>
                        <Button variant="ghost" size="sm">Manage</Button>
                      </NavLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      {/* Simple Modal */}
      {showModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100
        }}>
          <Card style={{ width: '400px' }}>
            <CardHeader>
              <CardTitle>Create New Workspace</CardTitle>
            </CardHeader>
            <CardBody>
              <form onSubmit={handleCreate} className="flex-col gap-4">
                <div className="flex-col gap-2">
                  <label className="text-sm font-medium">Name *</label>
                  <input className="glass-input" value={newName} onChange={e => setNewName(e.target.value)} required />
                </div>
                <div className="flex-col gap-2">
                  <label className="text-sm font-medium">Description</label>
                  <textarea className="glass-input" value={newDesc} onChange={e => setNewDesc(e.target.value)} rows={3} />
                </div>
                <div className="flex-row justify-between mt-4">
                  <Button type="button" variant="ghost" onClick={() => setShowModal(false)}>Cancel</Button>
                  <Button type="submit" isLoading={isCreating}>Create Workspace</Button>
                </div>
              </form>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
};
