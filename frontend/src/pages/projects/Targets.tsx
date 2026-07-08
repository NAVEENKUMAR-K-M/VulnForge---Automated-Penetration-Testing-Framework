import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Globe, Plus, Trash2 } from 'lucide-react';
import { targetsApi } from '../../api/targets';
import type { Target } from '../../api/targets';

export const ProjectTargets: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [targets, setTargets] = useState<Target[]>([]);
  const [newTarget, setNewTarget] = useState('');
  const [newTargetType, setNewTargetType] = useState('domain');

  useEffect(() => {
    if (id) loadTargets();
  }, [id]);

  const loadTargets = async () => {
    try {
      const data = await targetsApi.list(id!);
      setTargets(data);
    } catch (e) {
      console.error("Failed to load targets", e);
    }
  };

  const handleAddTarget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTarget.trim() || !id) return;
    try {
      await targetsApi.create(id, {
        target: newTarget,
        target_type: newTargetType as any,
        description: ''
      });
      setNewTarget('');
      loadTargets();
    } catch (e) {
      console.error("Failed to add target", e);
    }
  };

  const handleDeleteTarget = async (targetId: string) => {
    if (!id || !confirm('Are you sure you want to delete this target?')) return;
    try {
      await targetsApi.delete(id, targetId);
      loadTargets();
    } catch (e) {
      console.error("Failed to delete target", e);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-display font-bold text-white mb-2">Targets</h1>
          <p className="text-text-secondary">Manage the primary scopes for your security assessments.</p>
        </div>
      </div>

      <Card className="bg-surface-solid border-border-color">
        <CardBody className="p-6">
          <form onSubmit={handleAddTarget} className="flex gap-4">
            <select
              value={newTargetType}
              onChange={(e) => setNewTargetType(e.target.value)}
              className="bg-base border border-border-color rounded-md px-3 py-2 text-text-primary focus:outline-none focus:border-primary transition-colors"
            >
              <option value="domain">Domain</option>
              <option value="ip">IP Address</option>
              <option value="cidr">CIDR Range</option>
              <option value="github_org">GitHub Org</option>
            </select>
            <input
              type="text"
              placeholder="e.g. example.com"
              className="flex-1 bg-base border border-border-color rounded-md px-4 py-2 text-text-primary focus:outline-none focus:border-primary transition-colors"
              value={newTarget}
              onChange={(e) => setNewTarget(e.target.value)}
            />
            <Button type="submit" variant="primary" className="flex items-center gap-2">
              <Plus className="w-4 h-4" /> Add Target
            </Button>
          </form>
        </CardBody>
      </Card>

      <div className="grid gap-4">
        {targets.length === 0 ? (
          <div className="text-center py-12 text-text-muted bg-surface/50 rounded-lg border border-border-color border-dashed">
            <Globe className="w-12 h-12 mx-auto mb-3 opacity-20" />
            <p>No targets added yet.</p>
          </div>
        ) : (
          targets.map(t => (
            <Card key={t.id} className="bg-surface/50 border-border-color hover:border-border-color-hover transition-colors">
              <CardBody className="p-5 flex justify-between items-center">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-primary/10 rounded-lg text-primary">
                    <Globe className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white font-mono">{t.target}</h3>
                    <div className="flex items-center gap-3 mt-1">
                      <Badge variant="info" className="uppercase text-xs">{t.target_type}</Badge>
                      <span className="text-xs text-text-secondary">Added {new Date(t.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
                <Button variant="danger" onClick={() => handleDeleteTarget(t.id)} className="opacity-0 group-hover:opacity-100 transition-opacity p-2">
                  <Trash2 className="w-4 h-4" />
                </Button>
              </CardBody>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};
