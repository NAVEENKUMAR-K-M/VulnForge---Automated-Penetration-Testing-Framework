import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardBody } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { scanProfilesApi } from '../api/scanProfiles';
import type { ScanProfile } from '../api/scanProfiles';
import { Activity, Plus } from 'lucide-react';

export const ScanProfiles: React.FC = () => {
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [profileType, setProfileType] = useState('CUSTOM');

  const fetchProfiles = async () => {
    setIsLoading(true);
    try {
      const data = await scanProfilesApi.list();
      setProfiles(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await scanProfilesApi.create({
        name,
        description,
        profile_type: profileType,
        enabled_plugins: []
      });
      setShowModal(false);
      setName('');
      setDescription('');
      await fetchProfiles();
    } catch (err) {
      console.error(err);
      alert('Failed to create profile');
    }
  };

  return (
    <div className="flex-col gap-6" style={{ height: '100%' }}>
      <div className="flex-row items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Scan Profiles</h1>
          <p className="text-secondary">Manage predefined and custom scanning configurations.</p>
        </div>
        <Button leftIcon={<Plus size={18} />} onClick={() => setShowModal(true)}>New Profile</Button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '24px' }}>
        {isLoading ? (
          <p className="text-secondary">Loading profiles...</p>
        ) : (
          profiles.map(profile => (
            <Card key={profile.id} glass={false}>
              <CardHeader>
                <div className="flex-row justify-between w-full items-center">
                  <div className="flex-row items-center gap-2">
                    <Activity size={18} className="text-primary" />
                    <CardTitle>{profile.name}</CardTitle>
                  </div>
                  {profile.is_default && <Badge variant="primary">Default</Badge>}
                </div>
              </CardHeader>
              <CardBody className="flex-col gap-4 justify-between">
                <div>
                  <p className="text-sm text-secondary mb-3">{profile.description || 'No description provided.'}</p>
                  <div className="flex-row items-center gap-2 mb-2">
                    <span className="text-xs text-muted font-medium uppercase">Type</span>
                    <Badge variant="secondary">{profile.profile_type}</Badge>
                  </div>
                  <div className="flex-row items-center gap-2">
                    <span className="text-xs text-muted font-medium uppercase">Plugins</span>
                    <span className="text-sm">{profile.enabled_plugins?.length || 0} enabled</span>
                  </div>
                </div>
                <div className="flex-row gap-2 mt-4 pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
                  <Button variant="secondary" size="sm" style={{ flex: 1 }}>Edit Configuration</Button>
                </div>
              </CardBody>
            </Card>
          ))
        )}
      </div>

      {showModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100
        }}>
          <Card style={{ width: '400px' }}>
            <CardHeader>
              <CardTitle>Create Scan Profile</CardTitle>
            </CardHeader>
            <CardBody>
              <form onSubmit={handleCreate} className="flex-col gap-4">
                <div className="flex-col gap-2">
                  <label className="text-sm font-medium">Name *</label>
                  <input className="glass-input" value={name} onChange={e => setName(e.target.value)} required />
                </div>
                <div className="flex-col gap-2">
                  <label className="text-sm font-medium">Type</label>
                  <select className="glass-input" value={profileType} onChange={e => setProfileType(e.target.value)}>
                    <option value="CUSTOM">Custom</option>
                    <option value="QUICK_RECON">Quick Recon</option>
                    <option value="EXTERNAL_ASSESSMENT">External Assessment</option>
                  </select>
                </div>
                <div className="flex-col gap-2">
                  <label className="text-sm font-medium">Description</label>
                  <textarea className="glass-input" value={description} onChange={e => setDescription(e.target.value)} rows={3} />
                </div>
                <div className="flex-row justify-between mt-4">
                  <Button type="button" variant="ghost" onClick={() => setShowModal(false)}>Cancel</Button>
                  <Button type="submit">Create Profile</Button>
                </div>
              </form>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
};
