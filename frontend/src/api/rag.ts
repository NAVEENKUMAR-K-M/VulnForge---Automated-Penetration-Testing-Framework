import { fetchApi } from './client';

export interface RetrievalResult {
  writeup_id: string;
  chunk_id: string;
  chunk_index: number;
  content: string;
  similarity: number;
  title: string;
  source: string;
  source_url: string | null;
  vuln_class: string | null;
  cwe_id: string | null;
  tech_stack: string[];
}

export interface SearchResponse {
  query: string;
  results: RetrievalResult[];
  provider: string;
}

export interface RagStats {
  total_writeups: number;
  total_chunks: number;
  by_source: Record<string, number>;
  by_vuln_class: Record<string, number>;
  embedding_model: string;
  embedding_dim: number;
}

export interface IngestResult {
  ingested: number;
  skipped: number;
  chunks: number;
  provider: string;
}

export const ragApi = {
  search: (q: string, opts: { top_k?: number; vuln_class?: string; tech?: string } = {}): Promise<SearchResponse> => {
    const params = new URLSearchParams({ q });
    if (opts.top_k) params.set('top_k', String(opts.top_k));
    if (opts.vuln_class) params.set('vuln_class', opts.vuln_class);
    if (opts.tech) params.set('tech', opts.tech);
    return fetchApi<SearchResponse>(`/rag/search?${params.toString()}`);
  },

  stats: (): Promise<RagStats> => fetchApi<RagStats>('/rag/stats'),

  sources: (): Promise<{ sources: string[] }> => fetchApi<{ sources: string[] }>('/rag/sources'),

  ingestSource: (source: string, limit = 25): Promise<IngestResult> =>
    fetchApi<IngestResult>(`/rag/ingest/source?source=${encodeURIComponent(source)}&limit=${limit}`, {
      method: 'POST',
    }),

  ingestSeed: (): Promise<IngestResult> => fetchApi<IngestResult>('/rag/ingest/seed', { method: 'POST' }),
};
