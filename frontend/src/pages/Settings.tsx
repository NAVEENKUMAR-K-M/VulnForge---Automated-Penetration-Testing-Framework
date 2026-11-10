import React, { useState } from 'react';
import { User, KeyRound, LogOut } from 'lucide-react';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { PageHeader, Field, Input, ErrorBanner } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';

export const Settings: React.FC = () => {
  const { user, logout } = useAuth();
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const changePassword = async () => {
    if (!cur || !next) return;
    setBusy(true); setError(null); setOk(null);
    try {
      await authApi.changePassword({ current_password: cur, new_password: next });
      setOk('Password changed.');
      setCur(''); setNext('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <PageHeader eyebrow="Account" title="Settings" subtitle="Manage your profile and credentials." />
      <ErrorBanner message={error} />
      {ok && <div className="bg-success/10 border border-success/40 text-success rounded-lg px-4 py-3 text-sm mb-4">{ok}</div>}

      <div className="panel p-6 mb-6">
        <div className="flex items-center gap-2 mb-4"><User className="w-4 h-4 text-primary" /><h2 className="font-display font-semibold text-text-primary">Profile</h2></div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div><p className="text-xs uppercase tracking-wider text-text-muted">Name</p><p className="text-text-primary">{user?.full_name || '—'}</p></div>
          <div><p className="text-xs uppercase tracking-wider text-text-muted">Email</p><p className="data text-text-primary">{user?.email}</p></div>
          <div><p className="text-xs uppercase tracking-wider text-text-muted">Role</p><Badge variant={user?.is_superuser ? 'primary' : 'secondary'}>{user?.is_superuser ? 'Admin' : 'Analyst'}</Badge></div>
        </div>
      </div>

      <div className="panel p-6 mb-6">
        <div className="flex items-center gap-2 mb-4"><KeyRound className="w-4 h-4 text-primary" /><h2 className="font-display font-semibold text-text-primary">Change password</h2></div>
        <div className="space-y-4 max-w-sm">
          <Field label="Current password"><Input type="password" value={cur} onChange={(e) => setCur(e.target.value)} /></Field>
          <Field label="New password" hint="At least 12 characters."><Input type="password" value={next} onChange={(e) => setNext(e.target.value)} /></Field>
          <Button variant="primary" onClick={changePassword} isLoading={busy} disabled={!cur || !next}>Update password</Button>
        </div>
      </div>

      <Button variant="danger" leftIcon={<LogOut className="w-4 h-4" />} onClick={logout}>Sign out</Button>
    </div>
  );
};
