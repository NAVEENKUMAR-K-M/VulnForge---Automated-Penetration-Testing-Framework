import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardBody } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { authApi } from '../api/auth';
import type { UserResponse } from '../api/auth';
import { KeyRound, MonitorX, User } from 'lucide-react';

export const Settings: React.FC = () => {
  const [user, setUser] = useState<UserResponse | null>(null);
  
  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordMsg, setPasswordMsg] = useState<{ text: string, type: 'error' | 'success' } | null>(null);

  // Logout all devices state
  const [isLoggingOutAll, setIsLoggingOutAll] = useState(false);
  const [logoutAllMsg, setLogoutAllMsg] = useState<{ text: string, type: 'error' | 'success' } | null>(null);

  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const data = await authApi.getCurrentUser();
      setUser(data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMsg(null);
    
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ text: 'New passwords do not match', type: 'error' });
      return;
    }

    setIsChangingPassword(true);
    try {
      await authApi.changePassword({ 
        current_password: currentPassword, 
        new_password: newPassword 
      });
      setPasswordMsg({ text: 'Password changed successfully', type: 'success' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordMsg({ text: err.message || 'Failed to change password', type: 'error' });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleLogoutAll = async () => {
    if (!window.confirm("Are you sure you want to sign out from all other devices?")) return;
    
    setIsLoggingOutAll(true);
    setLogoutAllMsg(null);
    try {
      const res = await authApi.logoutAll();
      setLogoutAllMsg({ text: res.message || 'Successfully logged out all devices', type: 'success' });
    } catch (err: any) {
      setLogoutAllMsg({ text: err.message || 'Failed to logout from all devices', type: 'error' });
    } finally {
      setIsLoggingOutAll(false);
    }
  };

  if (!user) {
    return <div className="p-6">Loading profile...</div>;
  }

  return (
    <div className="flex-col gap-6" style={{ height: '100%', maxWidth: '800px', margin: '0 auto' }}>
      <div>
        <h1 className="text-3xl font-bold mb-2">Account Settings</h1>
        <p className="text-secondary">Manage your profile, security, and preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex-row items-center gap-2">
            <User size={18} className="text-primary" />
            <CardTitle>Profile Information</CardTitle>
          </div>
        </CardHeader>
        <CardBody className="flex-col gap-4">
          <div className="flex-col gap-1">
            <span className="text-sm font-medium text-secondary">Full Name</span>
            <span>{user.full_name || 'Not provided'}</span>
          </div>
          <div className="flex-col gap-1">
            <span className="text-sm font-medium text-secondary">Email Address</span>
            <span>{user.email}</span>
          </div>
          <div className="flex-col gap-1">
            <span className="text-sm font-medium text-secondary">Role</span>
            <span>{user.is_superuser ? 'Super Administrator' : 'Standard User'}</span>
          </div>
          <div className="flex-col gap-1">
            <span className="text-sm font-medium text-secondary">Member Since</span>
            <span>{new Date(user.created_at).toLocaleDateString()}</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex-row items-center gap-2">
            <KeyRound size={18} className="text-primary" />
            <CardTitle>Change Password</CardTitle>
          </div>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleChangePassword} className="flex-col gap-4">
            {passwordMsg && (
              <div style={{ 
                background: passwordMsg.type === 'error' ? 'var(--accent-danger-alpha)' : 'rgba(46, 160, 67, 0.1)', 
                color: passwordMsg.type === 'error' ? '#ff7b72' : '#3fb950', 
                padding: '8px 12px', borderRadius: '4px', fontSize: '14px', 
                border: `1px solid ${passwordMsg.type === 'error' ? 'rgba(248,81,73,0.3)' : 'rgba(46,160,67,0.3)'}` 
              }}>
                {passwordMsg.text}
              </div>
            )}
            
            <div className="flex-col gap-2">
              <label className="text-sm font-medium">Current Password</label>
              <input 
                type="password" 
                className="glass-input" 
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required 
              />
            </div>
            
            <div className="flex-col gap-2">
              <label className="text-sm font-medium">New Password</label>
              <input 
                type="password" 
                className="glass-input" 
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>

            <div className="flex-col gap-2">
              <label className="text-sm font-medium">Confirm New Password</label>
              <input 
                type="password" 
                className="glass-input" 
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required 
              />
            </div>
            
            <div className="flex-row justify-end mt-2">
              <Button type="submit" isLoading={isChangingPassword}>Update Password</Button>
            </div>
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex-row items-center gap-2">
            <MonitorX size={18} className="text-danger" />
            <CardTitle style={{ color: 'var(--accent-danger)' }}>Device Management</CardTitle>
          </div>
        </CardHeader>
        <CardBody className="flex-col gap-4">
          <p className="text-sm text-secondary">
            If you've noticed suspicious activity on your account, you can sign out of all active sessions across all devices. 
            You will need to sign back in on this device afterwards.
          </p>
          
          {logoutAllMsg && (
            <div style={{ 
              background: logoutAllMsg.type === 'error' ? 'var(--accent-danger-alpha)' : 'rgba(46, 160, 67, 0.1)', 
              color: logoutAllMsg.type === 'error' ? '#ff7b72' : '#3fb950', 
              padding: '8px 12px', borderRadius: '4px', fontSize: '14px', 
              border: `1px solid ${logoutAllMsg.type === 'error' ? 'rgba(248,81,73,0.3)' : 'rgba(46,160,67,0.3)'}` 
            }}>
              {logoutAllMsg.text}
            </div>
          )}
          
          <div className="flex-row justify-end">
            <Button 
              variant="secondary" 
              onClick={handleLogoutAll} 
              isLoading={isLoggingOutAll}
              style={{ color: 'var(--accent-danger)', borderColor: 'var(--accent-danger-alpha)' }}
            >
              Sign out from all devices
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
};
