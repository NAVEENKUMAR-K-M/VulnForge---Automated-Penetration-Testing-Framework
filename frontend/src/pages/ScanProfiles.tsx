import React, { useEffect, useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { Badge } from '../components/common/Badge';
import { PageHeader, Loading, ErrorBanner, EmptyState, DataTable } from '../components/ui';
import type { Column } from '../components/ui';
import { scanProfilesApi } from '../api/scanProfiles';
import type { ScanProfile } from '../api/scanProfiles';

export const ScanProfiles: React.FC = () => {
  const [rows, setRows] = useState<ScanProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    scanProfilesApi.list().then(setRows).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  const cols: Column<ScanProfile>[] = [
    { header: 'Profile', cell: (p) => <span className="text-text-primary font-medium">{p.name}</span> },
    { header: 'Type', cell: (p) => <Badge variant="secondary">{(p.profile_type || '').replace(/_/g, ' ')}</Badge> },
    { header: 'Description', cell: (p) => <span className="text-sm text-text-secondary">{p.description || '—'}</span> },
    { header: 'Plugins', cell: (p) => <span className="data text-xs">{p.enabled_plugins?.length ?? 0}</span> },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Configuration"
        title="Scan Profiles"
        subtitle="Reusable sets of tools and settings. Pick a profile when starting a scan to control which plugins run."
      />
      <ErrorBanner message={error} />
      {loading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState icon={<SlidersHorizontal className="w-12 h-12" />} title="No scan profiles" hint="Built-in profiles ship with the platform; none were found." />
      ) : (
        <DataTable columns={cols} rows={rows} keyFn={(p) => p.id} />
      )}
    </div>
  );
};
