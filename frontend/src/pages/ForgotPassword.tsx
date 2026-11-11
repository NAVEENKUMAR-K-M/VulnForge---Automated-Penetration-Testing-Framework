import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, Mail } from 'lucide-react';
import { Card, CardHeader, CardBody } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { authApi } from '../api/auth';

export const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string, type: 'error' | 'success' } | null>(null);

  const handleResetRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage(null);
    
    try {
      const res = await authApi.requestPasswordReset(email);
      setMessage({ text: res.message, type: 'success' });
      setEmail('');
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to request password reset', type: 'error' });
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
          <p className="text-secondary mt-2">Reset your password</p>
        </div>

        <Card>
          <CardHeader>
            <h2 className="text-xl font-semibold" style={{ margin: 0 }}>Forgot Password</h2>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleResetRequest} className="flex flex-col gap-4">
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
                <label className="text-sm font-medium text-secondary">Email address</label>
                <input 
                  type="email" 
                  className="glass-input" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required 
                />
              </div>
              
              <Button type="submit" size="lg" isLoading={isLoading} leftIcon={<Mail size={18} />} style={{ marginTop: 'var(--space-2)' }}>
                Send Reset Link
              </Button>
            </form>
          </CardBody>
        </Card>
        
        <div style={{ textAlign: 'center', marginTop: 'var(--space-4)' }}>
          <p className="text-secondary text-sm">
            Remembered your password? <Link to="/login" style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>Sign in here</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
