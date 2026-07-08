import React from 'react';
import { Outlet, NavLink, useParams } from 'react-router-dom';
import { LayoutDashboard, Target, Crosshair, Server, FileText, BarChart3, Settings } from 'lucide-react';

export const ProjectLayout: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const navigation = [
    { name: 'Dashboard', to: `/projects/${id}/dashboard`, icon: LayoutDashboard },
    { name: 'Targets', to: `/projects/${id}/targets`, icon: Target },
    { name: 'Scans', to: `/projects/${id}/scans`, icon: Crosshair },
    { name: 'Assets', to: `/projects/${id}/assets`, icon: Server },
    { name: 'Reports', to: `/projects/${id}/reports`, icon: FileText },
    { name: 'Charts', to: `/projects/${id}/charts`, icon: BarChart3 },
    { name: 'Settings', to: `/projects/${id}/settings`, icon: Settings },
  ];

  return (
    <div className="flex h-screen bg-base text-text-primary">
      {/* Sidebar */}
      <aside className="w-64 bg-surface-solid border-r border-border-color flex flex-col">
        <div className="p-6 border-b border-border-color">
          <h2 className="text-xl font-display font-bold text-white tracking-wide">VulnForge</h2>
        </div>
        
        <nav className="flex-1 overflow-y-auto py-4">
          <ul className="space-y-1 px-3">
            {navigation.map((item) => (
              <li key={item.name}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${
                      isActive 
                        ? 'bg-primary/20 text-primary font-medium' 
                        : 'text-text-secondary hover:bg-surface-hover hover:text-white'
                    }`
                  }
                >
                  <item.icon className="w-5 h-5" />
                  {item.name}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto">
        <div className="p-8 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
