import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldAlert, LogIn } from 'lucide-react';
import { Card, CardHeader, CardBody } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  
  const [email, setEmail] = useState('admin@vulnforge.com');
  const [password, setPassword] = useState('CHANGE_ME_ADMIN_PASSWORD');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    
    try {
      const { access_token } = await authApi.login(email, password);
      await login(access_token);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to login');
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
            background: 'linear-gradient(90deg, #fff, #8b949e)', 
            WebkitBackgroundClip: 'text', 
            WebkitTextFillColor: 'transparent' 
          }}>
            VulnForge
          </h1>
          <p className="text-secondary mt-2">Automated Penetration Testing</p>
        </div>

        <Card>
          <CardHeader>
            <h2 className="text-xl font-semibold" style={{ margin: 0 }}>Sign in</h2>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleLogin} className="flex-col gap-4">
              {error && (
                <div style={{ background: 'var(--accent-danger-alpha)', color: '#ff7b72', padding: '8px 12px', borderRadius: '4px', fontSize: '14px', border: '1px solid rgba(248,81,73,0.3)' }}>
                  {error}
                </div>
              )}
              <div className="flex-col gap-2">
                <label className="text-sm font-medium text-secondary">Email address</label>
                <input 
                  type="email" 
                  className="glass-input" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required 
                />
              </div>
              <div className="flex-col gap-2">
                <div className="flex-row justify-between items-center">
                  <label className="text-sm font-medium text-secondary">Password</label>
                  <Link to="/forgot-password" style={{ fontSize: '12px', color: 'var(--accent-primary)', textDecoration: 'none' }}>Forgot password?</Link>
                </div>
                <input 
                  type="password" 
                  className="glass-input" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required 
                />
              </div>
              
              <Button type="submit" size="lg" isLoading={isLoading} leftIcon={<LogIn size={18} />} style={{ marginTop: 'var(--space-2)' }}>
                Sign in
              </Button>
            </form>
          </CardBody>
        </Card>
        
        <div style={{ textAlign: 'center', marginTop: 'var(--space-4)' }}>
          <p className="text-secondary text-sm">
            Don't have an account? <Link to="/register" style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>Sign up here</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
