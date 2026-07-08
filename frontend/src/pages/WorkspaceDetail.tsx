import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardBody } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Globe, Server, ScanLine, SearchCode, Crosshair, Users, Settings as SettingsIcon } from 'lucide-react';
import { workspacesApi } from '../api/workspaces';
import type { Workspace, WorkspaceMember } from '../api/workspaces';
import { targetsApi } from '../api/targets';
import type { Target } from '../api/targets';
import { assetsApi } from '../api/assets';
import type { ReconAsset } from '../api/assets';
import { scopeApi } from '../api/scope';
import type { ScopeRule } from '../api/scope';
import { BASE_URL } from '../api/client';

const SecureImage: React.FC<{ url: string; alt?: string }> = ({ url, alt }) => {
  const [imgSrc, setImgSrc] = useState<string>('');
  const [error, setError] = useState(false);
  
  useEffect(() => {
    let objectUrl = '';
    const fetchImage = async () => {
      const token = localStorage.getItem('token');
      try {
        const response = await fetch(url, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        if (response.ok) {
          const blob = await response.blob();
          objectUrl = URL.createObjectURL(blob);
          setImgSrc(objectUrl);
        } else {
          setError(true);
        }
      } catch (e) {
        setError(true);
      }
    };
    fetchImage();
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);
  
  if (error) return <div className="text-muted text-xs p-4 bg-[var(--bg-secondary)] rounded flex items-center justify-center">Image failed to load</div>;
  if (!imgSrc) return <div className="text-muted text-xs p-4 bg-[var(--bg-secondary)] rounded flex items-center justify-center min-h-[100px] animate-pulse">Loading screenshot...</div>;
  
  return <img src={imgSrc} alt={alt || "Screenshot"} className="w-full h-auto max-h-96 object-contain rounded border border-[var(--border-color)] bg-black/5" />;
};

export const WorkspaceDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'targets' | 'assets' | 'scans' | 'scope' | 'members'>('targets');
  
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [assets, setAssets] = useState<ReconAsset[]>([]);
  const [scopeRules, setScopeRules] = useState<ScopeRule[]>([]);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Forms state
  const [newTarget, setNewTarget] = useState('');
  const [newTargetType, setNewTargetType] = useState('domain');
  
  const [newScopeRule, setNewScopeRule] = useState('');
  const [newScopeType, setNewScopeType] = useState('domain');
  const [newScopeIsInclude, setNewScopeIsInclude] = useState(true);

  // Member state
  const [newMemberEmail, setNewMemberEmail] = useState(''); // Would need user search in a real app
  const [newMemberRole, setNewMemberRole] = useState('viewer');

  // Settings modal state
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [editWsName, setEditWsName] = useState('');
  const [editWsDesc, setEditWsDesc] = useState('');

  useEffect(() => {
    if (id) {
      loadWorkspaceData();
    }
  }, [id]);

  const loadWorkspaceData = async () => {
    setIsLoading(true);
    try {
      const [ws, tgt, ast, scp, mem] = await Promise.all([
        workspacesApi.get(id!),
        targetsApi.list(id!),
        assetsApi.list(id!),
        scopeApi.list(id!),
        workspacesApi.listMembers(id!).catch(() => []) // Catch if not implemented in backend yet
      ]);
      setWorkspace(ws);
      setTargets(tgt);
      setAssets(ast);
      setScopeRules(scp);
      setMembers(mem);
      
      setEditWsName(ws.name);
      setEditWsDesc(ws.description || '');
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const updated = await workspacesApi.update(id!, { name: editWsName, description: editWsDesc });
      setWorkspace(updated);
      setShowSettingsModal(false);
    } catch (err) {
      console.error(err);
      alert('Failed to update workspace');
    }
  };

  const handleDeleteWorkspace = async () => {
    if (!window.confirm("Are you sure you want to delete this workspace? This cannot be undone.")) return;
    try {
      await workspacesApi.delete(id!);
      navigate('/workspaces');
    } catch (err) {
      console.error(err);
      alert('Failed to delete workspace');
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

  const handleDeleteTarget = async (targetId: string) => {
    try {
      await targetsApi.delete(id!, targetId);
      setTargets(targets.filter(t => t.id !== targetId));
    } catch (err) {
      console.error(err);
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

  const handleDeleteScope = async (ruleId: string) => {
    try {
      await scopeApi.delete(id!, ruleId);
      setScopeRules(scopeRules.filter(r => r.id !== ruleId));
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Note: newMemberEmail should ideally be a selected user_id from a user search dropdown
      // Assuming for this prototype we just have a text input that takes an ID
      await workspacesApi.addMember(id!, newMemberEmail, newMemberRole);
      setNewMemberEmail('');
      const mem = await workspacesApi.listMembers(id!);
      setMembers(mem);
    } catch (err) {
      console.error(err);
      alert('Failed to add member. Make sure you entered a valid User ID.');
    }
  };

  const handleRemoveMember = async (userId: string) => {
    try {
      await workspacesApi.removeMember(id!, userId);
      setMembers(members.filter(m => m.user_id !== userId));
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
          <Button variant="secondary" leftIcon={<SettingsIcon size={16} />} onClick={() => setShowSettingsModal(true)}>Settings</Button>
          <Button leftIcon={<ScanLine size={16} />}>New Scan</Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex-row gap-6" style={{ borderBottom: '1px solid var(--border-color)', overflowX: 'auto' }}>
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
        <button onClick={() => setActiveTab('members')} style={tabStyle('members')}>
          <Users size={18} /> Members ({members.length})
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
                <div key={a.id} className="glass-panel flex-col gap-3" style={{ padding: '16px' }}>
                  <div className="flex-row justify-between items-start">
                    <div>
                      <code className="text-primary text-lg">{a.value}</code>
                      <div className="text-xs text-muted mt-2">Found by: {a.source_tools?.join(', ') || 'Unknown'}</div>
                    </div>
                    <div className="flex-row items-center gap-2">
                      {a.metadata?.status_code && (
                        <Badge variant={
                          a.metadata.status_code < 300 ? 'success' : 
                          a.metadata.status_code < 400 ? 'warning' : 'danger'
                        }>
                          HTTP {a.metadata.status_code}
                        </Badge>
                      )}
                      <Badge variant="secondary">{a.asset_type}</Badge>
                    </div>
                  </div>
                  
                  {a.metadata && (Object.keys(a.metadata).length > 0) && (
                    <div className="flex-row flex-wrap gap-2 mt-2 pt-2" style={{ borderTop: '1px solid var(--border-color)' }}>
                      {a.metadata.title && (
                        <div className="text-sm text-secondary mr-4">
                          <strong>Title:</strong> {a.metadata.title}
                        </div>
                      )}
                      {a.metadata.redirect && (
                        <div className="text-sm text-secondary mr-4">
                          <strong>Redirects to:</strong> {a.metadata.redirect}
                        </div>
                      )}
                      {a.metadata.structured_tech ? (
                        <div className="flex-col gap-1 w-full mt-2">
                          {['cms', 'frameworks', 'languages', 'servers'].map(category => {
                            const items = a.metadata.structured_tech[category];
                            if (!items || items.length === 0) return null;
                            return (
                              <div key={category} className="flex-row flex-wrap gap-1 items-center">
                                <strong className="text-sm text-secondary w-24 capitalize">{category}:</strong>
                                {items.map((tech: string, i: number) => (
                                  <span key={i} className="text-xs" style={{ background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: '4px' }}>
                                    {tech}
                                  </span>
                                ))}
                              </div>
                            );
                          })}
                        </div>
                      ) : a.metadata.technologies && (
                        <div className="flex-row flex-wrap gap-1 items-center mt-2 w-full">
                          <strong className="text-sm text-secondary mr-1">Tech:</strong>
                          {a.metadata.technologies.slice(0, 10).map((tech: string, i: number) => (
                            <span key={i} className="text-xs" style={{ background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: '4px' }}>
                              {tech}
                            </span>
                          ))}
                          {a.metadata.technologies.length > 10 && (
                            <span className="text-xs text-muted">+{a.metadata.technologies.length - 10} more</span>
                          )}
                        </div>
                      )}
                      
                      {/* OS Detection (IP Assets) */}
                      {a.metadata.os_match && (
                        <div className="flex-row items-center gap-1">
                          <strong className="text-sm text-secondary mr-1">OS:</strong>
                          <span className="text-sm">{a.metadata.os_match}</span>
                          {a.metadata.os_accuracy && (
                            <span className="text-xs text-muted">({a.metadata.os_accuracy}% match)</span>
                          )}
                        </div>
                      )}

                      {/* Service/Port Detection (PORT Assets) */}
                      {a.metadata.service && (
                        <div className="text-sm text-secondary mr-4">
                          <strong>Service:</strong> <span className="text-primary">{a.metadata.service}</span>
                          {a.metadata.product && (
                            <span className="text-muted ml-1">
                              ({a.metadata.product} {a.metadata.version || ''})
                            </span>
                          )}
                        </div>
                      )}
                      {a.metadata.state && (
                        <div className="text-sm text-secondary mr-4">
                          <strong>State:</strong> 
                          <span className={a.metadata.state === 'open' ? 'text-success ml-1' : 'text-warning ml-1'}>
                            {a.metadata.state}
                          </span>
                        </div>
                      )}
                      
                      {/* Directory Enumeration Metadata (URL Assets) */}
                      {(a.metadata.content_length !== undefined || a.metadata.words !== undefined || a.metadata.lines !== undefined) && (
                        <div className="flex-row items-center gap-3 text-sm text-secondary">
                          {a.metadata.content_length !== undefined && (
                            <span><strong>Size:</strong> {a.metadata.content_length}</span>
                          )}
                          {a.metadata.words !== undefined && (
                            <span><strong>Words:</strong> {a.metadata.words}</span>
                          )}
                          {a.metadata.lines !== undefined && (
                            <span><strong>Lines:</strong> {a.metadata.lines}</span>
                          )}
                        </div>
                      )}
                      
                      {/* Screenshot Capture (Gowitness) */}
                      {a.metadata.screenshot_path && (
                        <div className="mt-4 w-full">
                          <strong className="text-sm text-secondary block mb-2">Screenshot:</strong>
                          <SecureImage url={`${BASE_URL}/workspaces/${id}/assets/${a.id}/screenshot`} />
                        </div>
                      )}
                    </div>
                  )}
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

          {activeTab === 'members' && (
            <div className="flex-col gap-6">
              <div>
                <p className="text-secondary mb-4">Manage users who have access to this workspace.</p>
                <form onSubmit={handleAddMember} className="flex-row gap-3 mb-6 items-center">
                  <input 
                    type="text" 
                    className="glass-input flex-1" 
                    placeholder="Enter User ID to invite..." 
                    value={newMemberEmail} 
                    onChange={e => setNewMemberEmail(e.target.value)} 
                    required 
                  />
                  <select 
                    className="glass-input" 
                    value={newMemberRole} 
                    onChange={e => setNewMemberRole(e.target.value)}
                    style={{ width: '150px' }}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="analyst">Analyst</option>
                    <option value="admin">Admin</option>
                  </select>
                  <Button type="submit">Add Member</Button>
                </form>
              </div>

              {(members || []).map(m => (
                <div key={m.user_id} className="glass-panel flex-row justify-between items-center" style={{ padding: '16px', marginBottom: '8px' }}>
                  <div>
                    <span className="font-medium">{m.user?.full_name || m.user?.email || m.user_id}</span>
                  </div>
                  <div className="flex-row items-center gap-4">
                    <Badge variant={m.role === 'admin' ? 'primary' : 'secondary'}>{m.role.toUpperCase()}</Badge>
                    <Button variant="danger" size="sm" onClick={() => handleRemoveMember(m.user_id)}>Remove</Button>
                  </div>
                </div>
              ))}
              {(members || []).length === 0 && <p className="text-muted">No additional members.</p>}
            </div>
          )}
        </CardBody>
      </Card>

      {/* Settings Modal */}
      {showSettingsModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100
        }}>
          <Card style={{ width: '500px' }}>
            <CardHeader>
              <CardTitle>Workspace Settings</CardTitle>
            </CardHeader>
            <CardBody>
              <form onSubmit={handleUpdateWorkspace} className="flex-col gap-4">
                <div className="flex-col gap-2">
                  <label className="text-sm font-medium">Workspace Name *</label>
                  <input 
                    className="glass-input" 
                    value={editWsName} 
                    onChange={e => setEditWsName(e.target.value)} 
                    required 
                  />
                </div>
                <div className="flex-col gap-2">
                  <label className="text-sm font-medium">Description</label>
                  <textarea 
                    className="glass-input" 
                    value={editWsDesc} 
                    onChange={e => setEditWsDesc(e.target.value)} 
                    rows={3} 
                  />
                </div>
                
                <div className="flex-row justify-between mt-4 items-center">
                  <Button type="button" variant="ghost" onClick={() => setShowSettingsModal(false)}>Cancel</Button>
                  <Button type="submit">Save Changes</Button>
                </div>
              </form>
              
              <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--accent-danger-alpha)' }}>
                <h3 className="text-sm font-medium text-danger mb-2">Danger Zone</h3>
                <p className="text-xs text-secondary mb-3">Deleting a workspace is irreversible and removes all associated data.</p>
                <Button 
                  type="button" 
                  variant="danger" 
                  style={{ width: '100%' }}
                  onClick={handleDeleteWorkspace}
                >
                  Delete Workspace
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
};
