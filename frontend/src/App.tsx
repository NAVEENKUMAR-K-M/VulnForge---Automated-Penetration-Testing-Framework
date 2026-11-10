import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import { ProjectLayout } from './components/layout/ProjectLayout';
import { Dashboard } from './pages/Dashboard';
import { Workspaces } from './pages/Workspaces';
import { ScanProfiles } from './pages/ScanProfiles';
import { KnowledgeBase } from './pages/KnowledgeBase';
import { Settings } from './pages/Settings';
import { ProjectDashboard } from './pages/projects/Dashboard';
import { ProjectTargets } from './pages/projects/Targets';
import { ProjectScope } from './pages/projects/Scope';
import { ProjectScans } from './pages/projects/Scans';
import { ProjectAgent } from './pages/projects/Agent';
import { ProjectAssets } from './pages/projects/Assets';
import { ProjectVulnerabilities } from './pages/projects/Vulnerabilities';
import { ProjectReports } from './pages/projects/Reports';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ForgotPassword } from './pages/ForgotPassword';
import { ResetPassword } from './pages/ResetPassword';
import { AuthProvider, useAuth } from './context/AuthContext';
import './index.css';

const AuthGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />

          <Route element={<AuthGuard><MainLayout /></AuthGuard>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/workspaces" element={<Workspaces />} />
            <Route path="/scan-profiles" element={<ScanProfiles />} />
            <Route path="/knowledge-base" element={<KnowledgeBase />} />
            <Route path="/settings" element={<Settings />} />
          </Route>

          <Route element={<AuthGuard><ProjectLayout /></AuthGuard>}>
            <Route path="/workspaces/:id" element={<Navigate to="dashboard" replace />} />
            <Route path="/projects/:id" element={<Navigate to="dashboard" replace />} />
            <Route path="/projects/:id/dashboard" element={<ProjectDashboard />} />
            <Route path="/projects/:id/targets" element={<ProjectTargets />} />
            <Route path="/projects/:id/scope" element={<ProjectScope />} />
            <Route path="/projects/:id/scans" element={<ProjectScans />} />
            <Route path="/projects/:id/agent" element={<ProjectAgent />} />
            <Route path="/projects/:id/assets" element={<ProjectAssets />} />
            <Route path="/projects/:id/vulnerabilities" element={<ProjectVulnerabilities />} />
            <Route path="/projects/:id/reports" element={<ProjectReports />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
