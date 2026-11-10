import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { FileText, Download, Sparkles } from 'lucide-react';
import { Button } from '../../components/common/Button';
import { PageHeader, StatCard, Loading, ErrorBanner } from '../../components/ui';
import { reportsApi } from '../../api/reports';
import type { ReportJson, ReportFormat } from '../../api/reports';

const FORMATS: { f: ReportFormat; label: string }[] = [
  { f: 'pdf', label: 'PDF' },
  { f: 'html', label: 'HTML' },
  { f: 'markdown', label: 'Markdown' },
  { f: 'json', label: 'JSON' },
];

export const ProjectReports: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ReportJson | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    reportsApi.getJson(id).then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  const download = async (f: ReportFormat) => {
    if (!id) return;
    setDownloading(f);
    try { await reportsApi.download(id, f); } catch (e: any) { setError(e.message); } finally { setDownloading(null); }
  };

  if (loading) return <Loading label="Generating report…" />;

  return (
    <div>
      <PageHeader
        eyebrow="Deliverable"
        title="Reports"
        subtitle="A professional assessment report with an AI executive summary, grounded in this workspace's findings."
        actions={
          <div className="flex gap-2">
            {FORMATS.map((x) => (
              <Button key={x.f} variant={x.f === 'pdf' ? 'primary' : 'secondary'} isLoading={downloading === x.f} leftIcon={<Download className="w-4 h-4" />} onClick={() => download(x.f)}>
                {x.label}
              </Button>
            ))}
          </div>
        }
      />
      <ErrorBanner message={error} />

      {data && (
        <>
          <div className="grid gap-4 sm:grid-cols-3 mb-6">
            <StatCard label="Assets" value={data.stats.total_assets} />
            <StatCard label="Vulnerabilities" value={data.stats.total_vulnerabilities} />
            <StatCard label="Critical / High" value={data.stats.critical_high_findings} tone={data.stats.critical_high_findings ? 'danger' : 'default'} />
          </div>

          <div className="panel p-6">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-primary" />
              <h2 className="font-display font-semibold text-text-primary">Executive summary</h2>
            </div>
            {data.executive_summary ? (
              <div className="space-y-3 text-text-secondary leading-relaxed">
                {data.executive_summary.split('\n\n').filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}
              </div>
            ) : (
              <p className="text-text-muted flex items-center gap-2"><FileText className="w-4 h-4" /> No summary available yet.</p>
            )}
          </div>
        </>
      )}
    </div>
  );
};
