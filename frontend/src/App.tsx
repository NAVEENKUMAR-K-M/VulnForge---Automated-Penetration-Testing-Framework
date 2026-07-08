import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import { ProjectLayout } from './components/layout/ProjectLayout';
import { Dashboard } from './pages/Dashboard';
import { Workspaces } from './pages/Workspaces';
import { ProjectDashboard } from './pages/projects/Dashboard';
import { ProjectTargets } from './pages/projects/Targets';
import { ProjectScans } from './pages/projects/Scans';
import { ProjectAssets } from './pages/projects/Assets';
import { ProjectReports } from './pages/projects/Reports';
import { ProjectCharts } from './pages/projects/Charts';
import { ScanProfiles } from './pages/ScanProfiles';
import { Settings } from './pages/Settings';
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
    return <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

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
          
          {/* Main Application Routes inside Layout */}
          <Route element={<AuthGuard><MainLayout /></AuthGuard>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/workspaces" element={<Workspaces />} />
            <Route path="/scan-profiles" element={<ScanProfiles />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          
          {/* Nested Project Routes inside ProjectLayout */}
          <Route element={<AuthGuard><ProjectLayout /></AuthGuard>}>
            <Route path="/workspaces/:id" element={<Navigate to="dashboard" replace />} />
            <Route path="/projects/:id" element={<Navigate to="dashboard" replace />} />
            <Route path="/projects/:id/dashboard" element={<ProjectDashboard />} />
            <Route path="/projects/:id/targets" element={<ProjectTargets />} />
            <Route path="/projects/:id/scans" element={<ProjectScans />} />
            <Route path="/projects/:id/assets" element={<ProjectAssets />} />
            <Route path="/projects/:id/reports" element={<ProjectReports />} />
            <Route path="/projects/:id/charts" element={<ProjectCharts />} />
            <Route path="/projects/:id/settings" element={<div className="p-8 text-white">Settings Placeholder</div>} />
          </Route>
          
          {/* Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
