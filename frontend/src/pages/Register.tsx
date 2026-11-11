import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldAlert, UserPlus } from 'lucide-react';
import { Card, CardHeader, CardBody } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';

export const Register: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);
    setError(null);
    
    try {
      const response = await authApi.register({ email, password, full_name: fullName });
      // The register endpoint returns a LoginResponse which includes access_token
      await login(response.tokens.access_token);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to register');
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
          <p className="text-secondary mt-2">Create a new account</p>
        </div>

        <Card>
          <CardHeader>
            <h2 className="text-xl font-semibold" style={{ margin: 0 }}>Register</h2>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleRegister} className="flex flex-col gap-4">
              {error && (
                <div style={{ background: 'var(--accent-danger-alpha)', color: '#ff7b72', padding: '8px 12px', borderRadius: '4px', fontSize: '14px', border: '1px solid rgba(248,81,73,0.3)' }}>
                  {error}
                </div>
              )}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-secondary">Full Name</label>
                <input 
                  type="text" 
                  className="glass-input" 
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required 
                />
              </div>
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
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-secondary">Password</label>
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
                <label className="text-sm font-medium text-secondary">Confirm Password</label>
                <input 
                  type="password" 
                  className="glass-input" 
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required 
                />
              </div>
              
              <Button type="submit" size="lg" isLoading={isLoading} leftIcon={<UserPlus size={18} />} style={{ marginTop: 'var(--space-2)' }}>
                Sign up
              </Button>
            </form>
          </CardBody>
        </Card>
        
        <div style={{ textAlign: 'center', marginTop: 'var(--space-4)' }}>
          <p className="text-secondary text-sm">
            Already have an account? <Link to="/login" style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>Sign in here</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
