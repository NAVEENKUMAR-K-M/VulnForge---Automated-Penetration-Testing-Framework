import React from 'react';
import { Search } from 'lucide-react';
import { openCommandPalette } from '../CommandPalette';

export const Topbar: React.FC<{ context?: string }> = ({ context }) => (
  <header className="sticky top-0 z-30 bg-surface/70 backdrop-blur-md border-b border-border-color h-14 flex items-center gap-4 px-6">
    <button
      onClick={openCommandPalette}
      className="group flex items-center gap-2 h-9 pl-3 pr-2 rounded-lg border border-border-color bg-base/40 text-text-muted hover:border-border-hover hover:text-text-secondary transition-colors w-72 max-w-full"
    >
      <Search className="w-4 h-4" />
      <span className="text-sm flex-1 text-left">Search or jump to…</span>
      <kbd className="data text-[0.65rem] border border-border-color rounded px-1.5 py-0.5 bg-surface">⌘K</kbd>
    </button>
    {context && <span className="text-sm text-text-muted truncate hidden sm:block">{context}</span>}
    <div className="ml-auto flex items-center gap-2">
      <span className="flex items-center gap-1.5 text-xs text-text-muted">
        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" /> Operational
      </span>
    </div>
  </header>
);
