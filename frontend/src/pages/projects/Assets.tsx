import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Server } from 'lucide-react';
import { Badge } from '../../components/common/Badge';
import { PageHeader, EmptyState, Loading, ErrorBanner, DataTable } from '../../components/ui';
import type { Column } from '../../components/ui';
import { assetsApi } from '../../api/assets';
import type { ReconAsset } from '../../api/assets';

export const ProjectAssets: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<ReconAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    assetsApi.list(id).then(setRows).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  const cols: Column<ReconAsset>[] = [
    { header: 'Type', cell: (a) => <Badge variant="secondary">{a.asset_type}</Badge> },
    { header: 'Value', cell: (a) => <span className="data text-text-primary">{a.value}</span> },
    {
      header: 'Service',
      cell: (a) => {
        const svc = a.metadata?.service;
        return svc ? <span className="data text-xs">{svc}{a.metadata?.product ? ` · ${a.metadata.product}` : ''}</span> : <span className="text-text-muted">—</span>;
      },
    },
    {
      header: 'Discovered by',
      cell: (a) => (
        <div className="flex flex-wrap gap-1">
          {(a.source_tools || []).map((t) => <span key={t} className="data text-xs px-2 py-0.5 rounded bg-surface-hover text-text-secondary">{t}</span>)}
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Discovery"
        title="Assets"
        subtitle="Hosts, ports, and services discovered by scans — deduplicated across tools."
      />
      <ErrorBanner message={error} />
      {loading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState icon={<Server className="w-12 h-12" />} title="No assets discovered yet" hint="Run a reconnaissance scan to populate the attack surface." />
      ) : (
        <DataTable columns={cols} rows={rows} keyFn={(a) => a.id} />
      )}
    </div>
  );
};
