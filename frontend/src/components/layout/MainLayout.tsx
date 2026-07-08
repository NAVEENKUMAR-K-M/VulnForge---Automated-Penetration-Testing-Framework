import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import './MainLayout.css';

export const MainLayout: React.FC = () => {
  return (
    <div className="v-layout">
      <Sidebar />
      <main className="v-main-content">
        <header className="v-topbar glass-panel">
          <div className="topbar-search">
            <input type="text" placeholder="Search workspaces, targets, scans..." className="glass-input" />
          </div>
          <div className="topbar-actions">
            <div className="user-avatar">AD</div>
          </div>
        </header>
        <div className="v-page-container">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
