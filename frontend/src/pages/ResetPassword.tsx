import React, { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { ShieldAlert, KeyRound } from 'lucide-react';
import { Card, CardHeader, CardBody } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { authApi } from '../api/auth';

export const ResetPassword: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string, type: 'error' | 'success' } | null>(null);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setMessage({ text: 'Passwords do not match', type: 'error' });
      return;
    }

    if (!token) {
      setMessage({ text: 'No reset token found in URL', type: 'error' });
      return;
    }

    setIsLoading(true);
    setMessage(null);
    
    try {
      const res = await authApi.confirmPasswordReset({ token, new_password: password });
      setMessage({ text: res.message, type: 'success' });
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to reset password', type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: 'var(--space-4)' }}>
      <div style={{ width: '100%', maxWidth: '400px' }}>
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-6)' }}>
          <ShieldAlert size={48} className="text-primary" style={{ margin: '0 auto var(--space-3)' }} />
          <h1 className="text-3xl font-bold" style={{ 
            background: 'none', color: 'var(--text-primary)', 
            WebkitBackgroundClip: 'text', 
            WebkitTextFillColor: 'currentColor' 
          }}>
            VulnForge
          </h1>
          <p className="text-secondary mt-2">Enter new password</p>
        </div>

        <Card>
          <CardHeader>
            <h2 className="text-xl font-semibold" style={{ margin: 0 }}>Reset Password</h2>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleReset} className="flex flex-col gap-4">
              {message && (
                <div style={{ 
                  background: message.type === 'error' ? 'var(--accent-danger-alpha)' : 'rgba(46, 160, 67, 0.1)', 
                  color: message.type === 'error' ? '#ff7b72' : '#3fb950', 
                  padding: '8px 12px', borderRadius: '4px', fontSize: '14px', 
                  border: `1px solid ${message.type === 'error' ? 'rgba(248,81,73,0.3)' : 'rgba(46,160,67,0.3)'}` 
                }}>
                  {message.text}
                </div>
              )}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-secondary">New Password</label>
                <input 
                  type="password" 
                  className="glass-input" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required 
                  minLength={8}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-secondary">Confirm New Password</label>
                <input 
                  type="password" 
                  className="glass-input" 
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required 
                />
              </div>
              
              <Button type="submit" size="lg" isLoading={isLoading} leftIcon={<KeyRound size={18} />} style={{ marginTop: 'var(--space-2)' }}>
                Reset Password
              </Button>
            </form>
          </CardBody>
        </Card>
        
        <div style={{ textAlign: 'center', marginTop: 'var(--space-4)' }}>
          <p className="text-secondary text-sm">
            <Link to="/login" style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>Return to Login</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
