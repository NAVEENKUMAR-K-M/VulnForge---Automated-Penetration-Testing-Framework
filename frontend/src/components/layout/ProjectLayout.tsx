import React, { useEffect, useState } from 'react';
import { Outlet, useParams, Link, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  LayoutDashboard, Crosshair, ShieldCheck, Radar, Bot, Server, Bug, FileText, ChevronLeft, ShieldHalf,
} from 'lucide-react';
import { workspacesApi } from '../../api/workspaces';
import { NavItem } from './Sidebar';
import { Topbar } from './Topbar';
import { CommandPalette } from '../CommandPalette';

export const ProjectLayout: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const [name, setName] = useState('Workspace');

  useEffect(() => {
    if (id) workspacesApi.get(id).then((w) => setName(w.name)).catch(() => {});
  }, [id]);

  const nav = [
    { name: 'Overview', to: `/projects/${id}/dashboard`, icon: LayoutDashboard },
    { name: 'Targets', to: `/projects/${id}/targets`, icon: Crosshair },
    { name: 'Scope', to: `/projects/${id}/scope`, icon: ShieldCheck },
    { name: 'Scans', to: `/projects/${id}/scans`, icon: Radar },
    { name: 'AI Agent', to: `/projects/${id}/agent`, icon: Bot },
    { name: 'Assets', to: `/projects/${id}/assets`, icon: Server },
    { name: 'Vulnerabilities', to: `/projects/${id}/vulnerabilities`, icon: Bug },
    { name: 'Reports', to: `/projects/${id}/reports`, icon: FileText },
  ];

  return (
    <div className="flex h-screen bg-base text-text-primary">
      <aside className="w-60 shrink-0 bg-surface border-r border-border-color flex flex-col">
        <div className="px-5 h-16 flex items-center gap-2.5 border-b border-border-color">
          <div className="w-8 h-8 rounded-lg bg-ink flex items-center justify-center">
            <ShieldHalf className="w-[18px] h-[18px] text-white" />
          </div>
          <span className="font-display font-semibold text-lg tracking-tight">VulnForge</span>
        </div>

        <div className="px-4 py-4 border-b border-border-color">
          <Link to="/workspaces" className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-primary mb-2">
            <ChevronLeft className="w-3.5 h-3.5" /> All workspaces
          </Link>
          <p className="text-[0.65rem] uppercase tracking-widest text-text-muted">Workspace</p>
          <p className="font-display font-semibold text-text-primary truncate" title={name}>{name}</p>
        </div>

        <nav className="flex-1 overflow-y-auto p-3">
          <div className="space-y-1">
            {nav.map((item) => <NavItem key={item.name} to={item.to} label={item.name} icon={item.icon} pillId="ws-nav-pill" />)}
          </div>
        </nav>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <Topbar context={name} />
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="max-w-7xl mx-auto px-8 py-8"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      <CommandPalette />
    </div>
  );
};
