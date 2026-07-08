import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardBody } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Globe, Server, ScanLine, SearchCode, Crosshair } from 'lucide-react';
import { workspacesApi } from '../api/workspaces';
import type { Workspace } from '../api/workspaces';
import { targetsApi } from '../api/targets';
import type { Target } from '../api/targets';
import { assetsApi } from '../api/assets';
import type { ReconAsset } from '../api/assets';
import { scopeApi } from '../api/scope';
import type { ScopeRule } from '../api/scope';

export const WorkspaceDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<'targets' | 'assets' | 'scans' | 'scope'>('targets');
  
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [assets, setAssets] = useState<ReconAsset[]>([]);
  const [scopeRules, setScopeRules] = useState<ScopeRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Forms state
  const [newTarget, setNewTarget] = useState('');
  const [newTargetType, setNewTargetType] = useState('domain');
  
  const [newScopeRule, setNewScopeRule] = useState('');
  const [newScopeType, setNewScopeType] = useState('domain');
  const [newScopeIsInclude, setNewScopeIsInclude] = useState(true);

  useEffect(() => {
    if (id) {
      loadWorkspaceData();
    }
  }, [id]);

  const loadWorkspaceData = async () => {
    setIsLoading(true);
    try {
      const [ws, tgt, ast, scp] = await Promise.all([
        workspacesApi.get(id!),
        targetsApi.list(id!),
        assetsApi.list(id!),
        scopeApi.list(id!)
      ]);
      setWorkspace(ws);
      setTargets(tgt);
      setAssets(ast);
      setScopeRules(scp);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddTarget = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await targetsApi.create(id!, { name: newTarget, value: newTarget, target_type: newTargetType });
      setNewTarget('');
      const tgt = await targetsApi.list(id!);
      setTargets(tgt);
    } catch (err) {
      console.error(err);
      alert('Failed to add target');
    }
  };

  const handleAddScopeRule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await scopeApi.create(id!, { 
        value: newScopeRule, 
        rule_type: newScopeType, 
        disposition: newScopeIsInclude ? 'allow' : 'exclude'
      });
      setNewScopeRule('');
      const scp = await scopeApi.list(id!);
      setScopeRules(scp);
    } catch (err) {
      console.error(err);
      alert('Failed to add scope rule');
    }
  };

  const handleDeleteTarget = async (targetId: string) => {
    try {
      await targetsApi.delete(id!, targetId);
      setTargets(targets.filter(t => t.id !== targetId));
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteScope = async (ruleId: string) => {
    try {
      await scopeApi.delete(id!, ruleId);
      setScopeRules(scopeRules.filter(r => r.id !== ruleId));
    } catch (err) {
      console.error(err);
    }
  };

  if (isLoading || !workspace) {
    return <div className="p-6">Loading workspace details...</div>;
  }

  const tabStyle = (tab: string) => ({
    background: 'none', border: 'none', padding: 'var(--space-3) 0', 
    color: activeTab === tab ? 'var(--accent-primary)' : 'var(--text-secondary)',
    borderBottom: activeTab === tab ? '2px solid var(--accent-primary)' : '2px solid transparent',
    fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px'
  });

  return (
    <div className="flex-col gap-6" style={{ height: '100%' }}>
      <div className="flex-row items-center justify-between">
        <div>
          <div className="flex-row items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold">{workspace.name}</h1>
            <Badge variant="success">Active</Badge>
          </div>
          <p className="text-secondary">{workspace.description || `Workspace ID: ${id}`}</p>
        </div>
        <div className="flex-row gap-3">
          <Button variant="secondary">Settings</Button>
          <Button leftIcon={<ScanLine size={16} />}>New Scan</Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex-row gap-6" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <button onClick={() => setActiveTab('targets')} style={tabStyle('targets')}>
          <Globe size={18} /> Targets ({targets.length})
        </button>
        <button onClick={() => setActiveTab('scope')} style={tabStyle('scope')}>
          <Crosshair size={18} /> Scope Rules ({scopeRules.length})
        </button>
        <button onClick={() => setActiveTab('assets')} style={tabStyle('assets')}>
          <Server size={18} /> Discovered Assets ({assets.length})
        </button>
        <button onClick={() => setActiveTab('scans')} style={tabStyle('scans')}>
          <SearchCode size={18} /> Scans (0)
        </button>
      </div>

      {/* Tab Content */}
      <Card glass={false} style={{ flex: 1 }}>
        <CardBody>
          {activeTab === 'targets' && (
            <div className="flex-col gap-6">
              <div>
                <p className="text-secondary mb-4">Explicitly defined in-scope targets for this workspace.</p>
                <form onSubmit={handleAddTarget} className="flex-row gap-3 mb-6">
                  <select 
                    className="glass-input" 
                    value={newTargetType} 
                    onChange={e => setNewTargetType(e.target.value)}
                    style={{ width: '150px' }}
                  >
                    <option value="domain">Domain</option>
                    <option value="host">IP Address</option>
                    <option value="network">CIDR</option>
                    <option value="url">URL</option>
                  </select>
                  <input 
                    type="text" 
                    className="glass-input flex-1" 
                    placeholder="e.g. example.com" 
                    value={newTarget} 
                    onChange={e => setNewTarget(e.target.value)} 
                    required 
                  />
                  <Button type="submit">Add Target</Button>
                </form>
              </div>

              {(targets || []).map(t => (
                <div key={t.id} className="glass-panel flex-row justify-between items-center" style={{ padding: '16px', marginBottom: '8px' }}>
                  <div>
                    <code className="text-primary">{t.value}</code> <Badge variant="primary" style={{ marginLeft: 8 }}>{t.target_type}</Badge>
                  </div>
                  <Button variant="danger" size="sm" onClick={() => handleDeleteTarget(t.id)}>Remove</Button>
                </div>
              ))}
              {(targets || []).length === 0 && <p className="text-muted">No targets defined yet.</p>}
            </div>
          )}

          {activeTab === 'scope' && (
            <div className="flex-col gap-6">
              <div>
                <p className="text-secondary mb-4">Define granular rules for what is explicitly allowed or denied during scans.</p>
                <form onSubmit={handleAddScopeRule} className="flex-row gap-3 mb-6 items-center">
                  <select 
                    className="glass-input" 
                    value={newScopeIsInclude ? 'include' : 'exclude'} 
                    onChange={e => setNewScopeIsInclude(e.target.value === 'include')}
                    style={{ width: '150px' }}
                  >
                    <option value="include">Include</option>
                    <option value="exclude">Exclude</option>
                  </select>
                  <select 
                    className="glass-input" 
                    value={newScopeType} 
                    onChange={e => setNewScopeType(e.target.value)}
                    style={{ width: '150px' }}
                  >
                    <option value="domain">Domain</option>
                    <option value="subdomain">Subdomain</option>
                    <option value="host">IP Address</option>
                    <option value="cidr">CIDR</option>
                    <option value="wildcard">Wildcard</option>
                  </select>
                  <input 
                    type="text" 
                    className="glass-input flex-1" 
                    placeholder="e.g. *.dev.example.com" 
                    value={newScopeRule} 
                    onChange={e => setNewScopeRule(e.target.value)} 
                    required 
                  />
                  <Button type="submit">Add Rule</Button>
                </form>
              </div>

              {(scopeRules || []).map(r => (
                <div key={r.id} className="glass-panel flex-row justify-between items-center" style={{ padding: '16px', marginBottom: '8px' }}>
                  <div>
                    <Badge variant={r.disposition === 'allow' ? 'success' : 'danger'} style={{ marginRight: 12 }}>
                      {r.disposition === 'allow' ? 'IN SCOPE' : 'OUT OF SCOPE'}
                    </Badge>
                    <code className="text-primary">{r.value}</code> 
                    <Badge variant="secondary" style={{ marginLeft: 8 }}>{r.rule_type}</Badge>
                  </div>
                  <Button variant="danger" size="sm" onClick={() => handleDeleteScope(r.id)}>Remove</Button>
                </div>
              ))}
              {(scopeRules || []).length === 0 && <p className="text-muted">No scope rules defined yet.</p>}
            </div>
          )}
          
          {activeTab === 'assets' && (
            <div className="flex-col gap-4">
              <p className="text-secondary mb-4">Assets discovered passively or actively by recon tools.</p>
              {(assets || []).map(a => (
                <div key={a.id} className="glass-panel flex-row justify-between items-center" style={{ padding: '16px' }}>
                  <div>
                    <code className="text-primary">{a.value}</code>
                    <div className="text-xs text-muted mt-1">Found by: {(a.source_tools || []).join(', ')}</div>
                  </div>
                  <Badge variant="secondary">{a.asset_type}</Badge>
                </div>
              ))}
              {(assets || []).length === 0 && <p className="text-muted">No assets discovered yet. Run a recon scan first.</p>}
            </div>
          )}

          {activeTab === 'scans' && (
            <div className="flex-col gap-4">
              <p className="text-secondary">Running and historical scans.</p>
              <div className="glass-panel" style={{ padding: '32px', textAlign: 'center' }}>
                <p className="text-muted">No scans run yet.</p>
                <Button style={{ marginTop: '16px' }}>Start First Scan</Button>
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
};
