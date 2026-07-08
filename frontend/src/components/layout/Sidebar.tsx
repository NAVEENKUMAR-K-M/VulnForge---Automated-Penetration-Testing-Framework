import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FolderKanban, ShieldAlert, Settings, LogOut, Activity } from 'lucide-react';
import './Sidebar.css';

export const Sidebar: React.FC = () => {
  return (
    <aside className="v-sidebar glass-panel">
      <div className="v-sidebar-header">
        <ShieldAlert size={28} className="text-primary" />
        <h2>VulnForge</h2>
      </div>
      
      <nav className="v-sidebar-nav">
        <div className="nav-group">
          <p className="nav-group-title">Main</p>
          <NavLink to="/dashboard" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/workspaces" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <FolderKanban size={18} />
            <span>Workspaces</span>
          </NavLink>
          <NavLink to="/scan-profiles" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <Activity size={18} />
            <span>Scan Profiles</span>
          </NavLink>
        </div>
      </nav>

      <div className="v-sidebar-footer">
        <NavLink to="/settings" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
          <Settings size={18} />
          <span>Settings</span>
        </NavLink>
        <button className="nav-item text-danger" onClick={() => {
          localStorage.removeItem('token');
          window.location.href = '/login';
        }}>
          <LogOut size={18} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
};
