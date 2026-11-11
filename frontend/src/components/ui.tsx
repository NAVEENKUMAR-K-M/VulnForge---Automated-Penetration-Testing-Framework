import React from 'react';
import type { ReactNode, InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { Loader2, X } from 'lucide-react';
import { motion } from 'framer-motion';
import { Badge } from './common/Badge';
import { CountUp } from './motion';

/* ── Page header ─────────────────────────────────────────────────────────── */
export const PageHeader: React.FC<{
  title: string;
  subtitle?: string;
  eyebrow?: string;
  actions?: ReactNode;
}> = ({ title, subtitle, eyebrow, actions }) => (
  <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
    <div>
      {eyebrow && (
        <div className="data text-xs uppercase tracking-widest text-primary/80 mb-2">{eyebrow}</div>
      )}
      <h1 className="text-2xl font-display font-semibold text-text-primary">{title}</h1>
      {subtitle && <p className="text-text-secondary mt-1 max-w-2xl">{subtitle}</p>}
    </div>
    {actions && <div className="flex items-center gap-2">{actions}</div>}
  </div>
);

/* ── Spinner / loading ───────────────────────────────────────────────────── */
export const Spinner: React.FC<{ className?: string }> = ({ className = 'w-5 h-5' }) => (
  <Loader2 className={`animate-spin text-primary ${className}`} />
);

export const Loading: React.FC<{ label?: string }> = ({ label = 'Loading…' }) => (
  <div className="flex items-center justify-center gap-3 py-16 text-text-secondary">
    <Spinner /> <span>{label}</span>
  </div>
);

/* ── Empty state ─────────────────────────────────────────────────────────── */
export const EmptyState: React.FC<{
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}> = ({ icon, title, hint, action }) => (
  <div className="text-center py-16 px-6 rounded-2xl border border-dashed border-border-color bg-surface/40">
    {icon && <div className="mx-auto mb-4 w-12 h-12 flex items-center justify-center text-text-muted">{icon}</div>}
    <p className="text-lg font-medium text-text-primary">{title}</p>
    {hint && <p className="text-sm text-text-secondary mt-1 max-w-md mx-auto">{hint}</p>}
    {action && <div className="mt-5 flex justify-center">{action}</div>}
  </div>
);

/* ── Stat card ───────────────────────────────────────────────────────────── */
export const StatCard: React.FC<{
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  tone?: 'default' | 'primary' | 'danger' | 'warning' | 'success';
}> = ({ label, value, icon, tone = 'default' }) => {
  const toneColor: Record<string, string> = {
    default: 'text-text-primary',
    primary: 'text-primary',
    danger: 'text-danger',
    warning: 'text-warning',
    success: 'text-success',
  };
  const toneBar: Record<string, string> = {
    default: 'var(--color-primary)',
    primary: 'var(--color-primary)',
    danger: 'var(--color-danger)',
    warning: 'var(--color-warning)',
    success: 'var(--color-success)',
  };
  const isNum = typeof value === 'number';
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ type: 'spring', stiffness: 300, damping: 22 }}
      className="panel panel-interactive p-5 relative overflow-hidden"
    >
      <div className="absolute left-0 top-0 bottom-0 w-[3px]" style={{ background: toneBar[tone], opacity: tone === 'default' ? 0.35 : 0.9 }} />
      <div className="flex items-start justify-between">
        <span className="text-xs uppercase tracking-wider text-text-muted">{label}</span>
        {icon && <span className="text-text-muted">{icon}</span>}
      </div>
      <div className={`mt-3 text-3xl font-display font-semibold tabular-nums ${toneColor[tone]}`}>
        {isNum ? <CountUp value={value} /> : value}
      </div>
    </motion.div>
  );
};

/* ── Data table ──────────────────────────────────────────────────────────── */
export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
  className?: string;
  width?: string;
}
export function DataTable<T>({
  columns,
  rows,
  keyFn,
  onRowClick,
}: {
  columns: Column<T>[];
  rows: T[];
  keyFn: (row: T) => string;
  onRowClick?: (row: T) => void;
}) {
  return (
    <div className="panel overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-border-color">
              {columns.map((c, i) => (
                <th
                  key={i}
                  className={`text-left font-medium text-xs uppercase tracking-wider text-text-muted px-4 py-3 ${c.className || ''}`}
                  style={c.width ? { width: c.width } : undefined}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={keyFn(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`border-b border-border-color/60 last:border-0 transition-colors ${
                  onRowClick ? 'cursor-pointer hover:bg-surface-hover' : ''
                }`}
              >
                {columns.map((c, i) => (
                  <td key={i} className={`px-4 py-3 text-text-secondary align-middle ${c.className || ''}`}>
                    {c.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Severity / status badges ────────────────────────────────────────────── */
const SEVERITY_META: Record<string, { label: string; color: string }> = {
  critical: { label: 'Critical', color: 'var(--color-critical)' },
  high: { label: 'High', color: 'var(--color-high)' },
  medium: { label: 'Medium', color: 'var(--color-medium)' },
  low: { label: 'Low', color: 'var(--color-low)' },
  info: { label: 'Info', color: 'var(--color-info)' },
};
export const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const m = SEVERITY_META[severity?.toLowerCase()] || SEVERITY_META.info;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide px-2.5 py-0.5 rounded-full"
      style={{ color: m.color, background: `color-mix(in srgb, ${m.color} 14%, transparent)`, border: `1px solid color-mix(in srgb, ${m.color} 36%, transparent)` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: m.color }} />
      {m.label}
    </span>
  );
};

type BadgeVariant = 'primary' | 'secondary' | 'success' | 'warning' | 'danger';
export const StatusBadge: React.FC<{ status: string; map?: Record<string, BadgeVariant> }> = ({ status, map }) => {
  const defaults: Record<string, BadgeVariant> = {
    completed: 'success', running: 'primary', pending: 'secondary', failed: 'danger',
    cancelled: 'secondary', awaiting_approval: 'warning', active: 'success', open: 'danger',
    executed: 'success', skipped: 'secondary', proposed: 'warning', approved: 'primary', rejected: 'secondary',
  };
  const variant = (map && map[status]) || defaults[status] || 'secondary';
  return <Badge variant={variant}>{String(status).replace(/_/g, ' ')}</Badge>;
};

/* ── Form controls ───────────────────────────────────────────────────────── */
export const Field: React.FC<{ label: string; hint?: string; children: ReactNode }> = ({ label, hint, children }) => (
  <label className="flex flex-col gap-1.5">
    <span className="text-sm font-medium text-text-secondary">{label}</span>
    {children}
    {hint && <span className="text-xs text-text-muted">{hint}</span>}
  </label>
);

const controlClasses =
  'bg-base border border-border-color rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-primary focus:outline-none';

export const Input: React.FC<InputHTMLAttributes<HTMLInputElement>> = ({ className = '', ...p }) => (
  <input className={`${controlClasses} ${className}`} {...p} />
);
export const Select: React.FC<SelectHTMLAttributes<HTMLSelectElement>> = ({ className = '', children, ...p }) => (
  <select className={`${controlClasses} ${className}`} {...p}>{children}</select>
);
export const Textarea: React.FC<TextareaHTMLAttributes<HTMLTextAreaElement>> = ({ className = '', ...p }) => (
  <textarea className={`${controlClasses} resize-y min-h-[90px] ${className}`} {...p} />
);

/* ── Modal ───────────────────────────────────────────────────────────────── */
export const Modal: React.FC<{ open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode }> = ({
  open, onClose, title, children, footer,
}) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg panel vf-rise shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-color">
          <h3 className="text-lg font-display font-semibold text-text-primary">{title}</h3>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">{children}</div>
        {footer && <div className="px-5 py-4 border-t border-border-color flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
};

/* ── Inline error banner ─────────────────────────────────────────────────── */
export const ErrorBanner: React.FC<{ message: string | null }> = ({ message }) =>
  message ? (
    <div className="bg-danger/10 border border-danger/40 text-danger rounded-lg px-4 py-3 text-sm mb-4">{message}</div>
  ) : null;
