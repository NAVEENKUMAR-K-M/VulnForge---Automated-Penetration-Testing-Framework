import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { LogIn, ShieldHalf, Terminal } from 'lucide-react';
import { Button } from '../components/common/Button';
import { Field, Input, ErrorBanner } from '../components/ui';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('admin@vulnforge.com');
  const [password, setPassword] = useState('');
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
      setError(err.message || 'Sign in failed. Check your credentials and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Brand panel */}
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-border-color relative overflow-hidden">
        <div className="relative z-10 flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-ink flex items-center justify-center">
            <ShieldHalf className="w-5 h-5 text-white" />
          </div>
          <span className="font-display font-semibold text-xl">VulnForge</span>
        </div>
        <div className="relative z-10 max-w-md">
          <h1 className="text-4xl font-display font-semibold leading-tight text-gradient">
            The security operations console for automated assessment.
          </h1>
          <p className="text-text-secondary mt-4 leading-relaxed">
            Orchestrate reconnaissance, scanning, and an approval-gated AI agent — grounded in a knowledge base of real
            disclosed writeups.
          </p>
          <div className="data text-xs text-text-muted mt-8 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-primary" /> recon → scan → agent → report
          </div>
        </div>
        <div className="relative z-10 data text-xs text-text-muted">For authorized security testing only.</div>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2.5 mb-8 justify-center">
            <ShieldHalf className="w-6 h-6 text-primary" />
            <span className="font-display font-semibold text-xl">VulnForge</span>
          </div>
          <h2 className="text-2xl font-display font-semibold mb-1">Sign in</h2>
          <p className="text-text-secondary mb-6">Welcome back. Enter your credentials to continue.</p>

          <ErrorBanner message={error} />
          <form onSubmit={handleLogin} className="space-y-4">
            <Field label="Email">
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
            </Field>
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text-secondary">Password</span>
                <Link to="/forgot-password" className="text-xs text-primary">Forgot password?</Link>
              </div>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <Button type="submit" size="lg" isLoading={isLoading} leftIcon={<LogIn className="w-4 h-4" />} className="w-full">
              Sign in
            </Button>
          </form>

          <p className="text-text-secondary text-sm mt-6 text-center">
            Don't have an account? <Link to="/register" className="text-primary">Create one</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
