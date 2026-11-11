import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LayoutDashboard, FolderKanban, SlidersHorizontal, BookOpen, Settings, LogOut, ShieldHalf } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/workspaces', label: 'Workspaces', icon: FolderKanban },
  { to: '/scan-profiles', label: 'Scan Profiles', icon: SlidersHorizontal },
  { to: '/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
];

export const NavItem: React.FC<{ to: string; label: string; icon: React.ElementType; pillId: string }> = ({
  to, label, icon: Icon, pillId,
}) => (
  <NavLink to={to} className="block">
    {({ isActive }) => (
      <div className="relative px-3 py-2 rounded-lg">
        {isActive && (
          <motion.div
            layoutId={pillId}
            className="absolute inset-0 rounded-lg bg-primary/15 border border-primary/25"
            transition={{ type: 'spring', stiffness: 420, damping: 34 }}
          />
        )}
        <span className={`relative z-10 flex items-center gap-3 text-sm transition-colors ${isActive ? 'text-primary font-medium' : 'text-text-secondary hover:text-text-primary'}`}>
          <Icon className="w-[18px] h-[18px]" />
          {label}
        </span>
      </div>
    )}
  </NavLink>
);

export const Sidebar: React.FC = () => {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const initials = (user?.full_name || user?.email || 'U')
    .split(/[\s@._]/).filter(Boolean).slice(0, 2).map((s) => s[0]?.toUpperCase()).join('');

  return (
    <aside className="w-60 shrink-0 bg-surface border-r border-border-color flex flex-col">
      <div className="px-5 h-16 flex items-center gap-2.5 border-b border-border-color">
        <motion.div
          whileHover={{ rotate: -8, scale: 1.05 }}
          className="w-8 h-8 rounded-lg bg-ink flex items-center justify-center"
        >
          <ShieldHalf className="w-[18px] h-[18px] text-white" />
        </motion.div>
        <span className="font-display font-semibold text-lg tracking-tight text-text-primary">VulnForge</span>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        <p className="px-3 pb-2 text-[0.65rem] uppercase tracking-widest text-text-muted">Platform</p>
        <div className="space-y-1">
          {nav.map((n) => <NavItem key={n.to} {...n} pillId="main-nav-pill" />)}
        </div>
      </nav>

      <div className="p-3 border-t border-border-color space-y-1">
        <div className="flex items-center gap-2.5 px-2 py-2 mb-1">
          <div className="w-8 h-8 rounded-full bg-primary/15 border border-primary/25 flex items-center justify-center text-xs font-semibold text-primary">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-sm text-text-primary truncate">{user?.full_name || 'Operator'}</p>
            <p className="text-xs text-text-muted truncate">{user?.email}</p>
          </div>
        </div>
        <NavItem to="/settings" label="Settings" icon={Settings} pillId="main-nav-pill" />
        <button
          onClick={() => { logout(); navigate('/login'); }}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-text-secondary hover:bg-danger/10 hover:text-danger transition-colors"
        >
          <LogOut className="w-[18px] h-[18px]" />
          Sign out
        </button>
      </div>
    </aside>
  );
};
