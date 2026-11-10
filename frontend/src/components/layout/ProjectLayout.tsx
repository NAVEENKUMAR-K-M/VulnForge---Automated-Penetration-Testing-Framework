import React, { useEffect, useState } from 'react';
import { Outlet, NavLink, useParams, Link } from 'react-router-dom';
import {
  LayoutDashboard, Crosshair, ShieldCheck, Radar, Bot, Server, Bug, FileText, ChevronLeft, ShieldHalf,
} from 'lucide-react';
import { workspacesApi } from '../../api/workspaces';

export const ProjectLayout: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [name, setName] = useState<string>('Workspace');

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
      <aside className="w-60 shrink-0 bg-surface-solid border-r border-border-color flex flex-col">
        <div className="px-5 h-16 flex items-center gap-2.5 border-b border-border-color">
          <div className="w-8 h-8 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center">
            <ShieldHalf className="w-5 h-5 text-primary" />
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
          <ul className="space-y-1">
            {nav.map((item) => (
              <li key={item.name}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                      isActive
                        ? 'bg-primary/15 text-primary font-medium'
                        : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                    }`
                  }
                >
                  <item.icon className="w-[18px] h-[18px]" />
                  {item.name}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-8 py-8 vf-rise">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
