import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FolderKanban, SlidersHorizontal, BookOpen, ArrowRight, ShieldHalf } from 'lucide-react';
import { PageHeader, StatCard, Loading } from '../components/ui';
import { Stagger, StaggerItem, motion } from '../components/motion';
import { useAuth } from '../context/AuthContext';
import { workspacesApi } from '../api/workspaces';
import type { Workspace } from '../api/workspaces';

const quickLinks = [
  { to: '/workspaces', label: 'Workspaces', hint: 'Engagements, targets & scope', icon: FolderKanban },
  { to: '/scan-profiles', label: 'Scan Profiles', hint: 'Reusable tool configurations', icon: SlidersHorizontal },
  { to: '/knowledge-base', label: 'Knowledge Base', hint: 'Search disclosed writeups', icon: BookOpen },
];

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    workspacesApi.list().then(setWorkspaces).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const firstName = (user?.full_name || user?.email || 'Operator').split(/[\s@]/)[0];

  return (
    <div>
      <PageHeader
        eyebrow="Operations console"
        title={`Welcome back, ${firstName}`}
        subtitle="Orchestrate reconnaissance, scanning, and AI-assisted assessment across your engagements."
      />

      {loading ? (
        <Loading />
      ) : (
        <>
          <Stagger className="grid gap-4 sm:grid-cols-3 mb-8">
            <StaggerItem><StatCard label="Workspaces" value={workspaces.length} icon={<FolderKanban className="w-5 h-5" />} tone="primary" /></StaggerItem>
            <StaggerItem><StatCard label="Active engagements" value={workspaces.filter((w) => w.is_active !== false).length} icon={<ShieldHalf className="w-5 h-5" />} /></StaggerItem>
            <StaggerItem><StatCard label="Role" value={user?.is_superuser ? 'Admin' : 'Analyst'} /></StaggerItem>
          </Stagger>

          <h2 className="text-sm uppercase tracking-wider text-text-muted mb-3">Jump to</h2>
          <Stagger className="grid gap-4 sm:grid-cols-3 mb-8">
            {quickLinks.map((q) => (
              <StaggerItem key={q.to}>
                <motion.div whileHover={{ y: -4 }} transition={{ type: 'spring', stiffness: 300, damping: 22 }}>
                  <Link to={q.to} className="panel panel-interactive p-5 group flex items-start justify-between h-full">
                    <div>
                      <q.icon className="w-6 h-6 text-primary mb-3" />
                      <p className="font-medium text-text-primary">{q.label}</p>
                      <p className="text-sm text-text-secondary">{q.hint}</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                  </Link>
                </motion.div>
              </StaggerItem>
            ))}
          </Stagger>

          {workspaces.length > 0 && (
            <>
              <h2 className="text-sm uppercase tracking-wider text-text-muted mb-3">Recent workspaces</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {workspaces.slice(0, 4).map((w) => (
                  <Link key={w.id} to={`/projects/${w.id}/dashboard`} className="panel p-4 flex items-center justify-between hover:border-primary/50 transition-colors">
                    <div>
                      <p className="font-medium text-text-primary">{w.name}</p>
                      <p className="text-sm text-text-secondary line-clamp-1">{w.description || 'No description'}</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-text-muted" />
                  </Link>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
};
