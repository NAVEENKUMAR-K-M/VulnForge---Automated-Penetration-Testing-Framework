import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import {
  LayoutDashboard, FolderKanban, SlidersHorizontal, BookOpen, Settings, LogOut, Search, CornerDownLeft,
} from 'lucide-react';
import { workspacesApi } from '../api/workspaces';
import type { Workspace } from '../api/workspaces';
import { useAuth } from '../context/AuthContext';

/** Dispatch this to open the palette from anywhere. */
export const openCommandPalette = () => window.dispatchEvent(new CustomEvent('vf:command'));

export const CommandPalette: React.FC = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    const onEvt = () => setOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('vf:command', onEvt);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('vf:command', onEvt);
    };
  }, []);

  useEffect(() => {
    if (open && workspaces.length === 0) {
      workspacesApi.list().then(setWorkspaces).catch(() => {});
    }
  }, [open, workspaces.length]);

  const go = (to: string) => { setOpen(false); navigate(to); };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[18vh] px-4" onClick={() => setOpen(false)}>
      <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" />
      <Command
        className="relative w-full max-w-xl glass rounded-xl shadow-2xl overflow-hidden vf-rise"
        onClick={(e) => e.stopPropagation()}
        loop
      >
        <div className="flex items-center gap-2 px-4 border-b border-border-color">
          <Search className="w-4 h-4 text-text-muted" />
          <Command.Input
            autoFocus
            placeholder="Search commands, pages, workspaces…"
            className="flex-1 bg-transparent py-3.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
          />
          <kbd className="data text-[0.65rem] text-text-muted border border-border-color rounded px-1.5 py-0.5">ESC</kbd>
        </div>
        <Command.List className="max-h-[320px] overflow-y-auto p-2">
          <Command.Empty className="py-8 text-center text-sm text-text-muted">No results found.</Command.Empty>

          <Command.Group heading="Navigate" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[0.65rem] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-text-muted">
            <Item icon={LayoutDashboard} label="Dashboard" onSelect={() => go('/dashboard')} />
            <Item icon={FolderKanban} label="Workspaces" onSelect={() => go('/workspaces')} />
            <Item icon={SlidersHorizontal} label="Scan Profiles" onSelect={() => go('/scan-profiles')} />
            <Item icon={BookOpen} label="Knowledge Base" onSelect={() => go('/knowledge-base')} />
            <Item icon={Settings} label="Settings" onSelect={() => go('/settings')} />
          </Command.Group>

          {workspaces.length > 0 && (
            <Command.Group heading="Open workspace" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[0.65rem] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-text-muted">
              {workspaces.map((w) => (
                <Item key={w.id} icon={FolderKanban} label={w.name} onSelect={() => go(`/projects/${w.id}/dashboard`)} />
              ))}
            </Command.Group>
          )}

          <Command.Group heading="Account" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[0.65rem] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-text-muted">
            <Item icon={LogOut} label="Sign out" onSelect={() => { setOpen(false); logout(); navigate('/login'); }} />
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  );
};

const Item: React.FC<{ icon: React.ElementType; label: string; onSelect: () => void }> = ({ icon: Icon, label, onSelect }) => (
  <Command.Item
    onSelect={onSelect}
    className="group flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm text-text-secondary cursor-pointer data-[selected=true]:bg-primary/15 data-[selected=true]:text-primary"
  >
    <Icon className="w-4 h-4" />
    <span className="flex-1">{label}</span>
    <CornerDownLeft className="w-3.5 h-3.5 opacity-0 group-data-[selected=true]:opacity-100" />
  </Command.Item>
);
