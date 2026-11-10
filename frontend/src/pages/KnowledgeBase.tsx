import React, { useEffect, useState } from 'react';
import { Search, BookOpen, Database, Download, ExternalLink } from 'lucide-react';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { PageHeader, StatCard, ErrorBanner, Spinner, EmptyState, Input, Select } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { ragApi } from '../api/rag';
import type { RagStats, RetrievalResult } from '../api/rag';

export const KnowledgeBase: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<RagStats | null>(null);
  const [q, setQ] = useState('');
  const [results, setResults] = useState<RetrievalResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<string[]>([]);
  const [source, setSource] = useState('github_advisories');
  const [ingesting, setIngesting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const loadStats = () => ragApi.stats().then(setStats).catch(() => {});
  useEffect(() => {
    loadStats();
    ragApi.sources().then((s) => setSources(s.sources)).catch(() => {});
  }, []);

  const search = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!q.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const res = await ragApi.search(q, { top_k: 8 });
      setResults(res.results);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  };

  const ingest = async () => {
    setIngesting(true);
    setNotice(null);
    setError(null);
    try {
      const r = await ragApi.ingestSource(source, 15);
      setNotice(`Ingested ${r.ingested}, skipped ${r.skipped} (${r.chunks} chunks) from ${source}.`);
      loadStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Intelligence"
        title="Knowledge Base"
        subtitle="Semantic search over disclosed security writeups, advisories, and methodology — context for scans and the agent."
      />
      <ErrorBanner message={error} />

      {stats && (
        <div className="grid gap-4 sm:grid-cols-4 mb-6">
          <StatCard label="Writeups" value={stats.total_writeups} icon={<BookOpen className="w-5 h-5" />} tone="primary" />
          <StatCard label="Chunks" value={stats.total_chunks} icon={<Database className="w-5 h-5" />} />
          <StatCard label="Sources" value={Object.keys(stats.by_source).length} />
          <StatCard label="Embedding model" value={<span className="data text-sm leading-snug break-words block">{stats.embedding_model}</span>} />
        </div>
      )}

      {user?.is_superuser && (
        <div className="panel p-4 mb-6 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-text-secondary">Ingest source</span>
            <Select value={source} onChange={(e) => setSource(e.target.value)} className="min-w-[200px]">
              {sources.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
          </div>
          <Button variant="secondary" leftIcon={<Download className="w-4 h-4" />} isLoading={ingesting} onClick={ingest}>
            Ingest 15 writeups
          </Button>
          {notice && <span className="text-sm text-success">{notice}</span>}
        </div>
      )}

      <form onSubmit={search} className="flex gap-2 mb-6">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            className="w-full pl-9"
            placeholder="e.g. SSRF reaching cloud metadata, IDOR in an API…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <Button variant="primary" type="submit" isLoading={searching} disabled={!q.trim()}>Search</Button>
      </form>

      {searching ? (
        <div className="flex justify-center py-10"><Spinner /></div>
      ) : results === null ? (
        <EmptyState icon={<Search className="w-12 h-12" />} title="Search the corpus" hint="Describe a vulnerability or technique in plain language — results rank by semantic similarity." />
      ) : results.length === 0 ? (
        <EmptyState icon={<BookOpen className="w-12 h-12" />} title="No matches" hint="Try broader wording, or ingest more sources above." />
      ) : (
        <div className="space-y-3">
          {results.map((r) => (
            <div key={r.chunk_id} className="panel p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-medium text-text-primary">{r.title}</h3>
                  <Badge variant="secondary">{r.source}</Badge>
                  {r.vuln_class && <Badge variant="primary">{r.vuln_class}</Badge>}
                  {r.cwe_id && <span className="data text-xs text-text-muted">{r.cwe_id}</span>}
                </div>
                <span className="data text-xs text-primary shrink-0">{(r.similarity * 100).toFixed(0)}%</span>
              </div>
              <p className="text-sm text-text-secondary mt-2 line-clamp-3">{r.content}</p>
              {r.source_url && (
                <a href={r.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-primary mt-2">
                  Source <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
