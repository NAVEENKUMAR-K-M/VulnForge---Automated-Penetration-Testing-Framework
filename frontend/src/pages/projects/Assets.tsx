import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardBody } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { Server, Globe, Search } from 'lucide-react';
import { assetsApi } from '../../api/assets';
import type { ReconAsset } from '../../api/assets';
import { BASE_URL } from '../../api/client';

const SecureImage: React.FC<{ url: string; alt?: string }> = ({ url, alt }) => {
  const [imgSrc, setImgSrc] = useState<string>('');
  const [error, setError] = useState(false);
  
  useEffect(() => {
    let objectUrl = '';
    const fetchImage = async () => {
      const token = localStorage.getItem('token');
      try {
        const response = await fetch(url, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        if (response.ok) {
          const blob = await response.blob();
          objectUrl = URL.createObjectURL(blob);
          setImgSrc(objectUrl);
        } else {
          setError(true);
        }
      } catch (e) {
        setError(true);
      }
    };
    fetchImage();
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);
  
  if (error) return <div className="text-muted text-xs p-4 bg-surface rounded flex items-center justify-center">Image failed to load</div>;
  if (!imgSrc) return <div className="text-muted text-xs p-4 bg-surface rounded flex items-center justify-center min-h-[100px] animate-pulse">Loading screenshot...</div>;
  
  return <img src={imgSrc} alt={alt || "Screenshot"} className="w-full h-auto max-h-96 object-contain rounded border border-border-color bg-black/5" />;
};

export const ProjectAssets: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [assets, setAssets] = useState<ReconAsset[]>([]);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (id) loadAssets();
  }, [id]);

  const loadAssets = async () => {
    try {
      const data = await assetsApi.list(id!);
      setAssets(data);
    } catch (e) {
      console.error("Failed to load assets", e);
    }
  };

  const filteredAssets = assets.filter(a => a.value.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-display font-bold text-white mb-2">Discovered Assets</h1>
          <p className="text-text-secondary">Explore the external attack surface discovered during reconnaissance.</p>
        </div>
      </div>

      <div className="relative">
        <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-text-muted" />
        <input 
          type="text" 
          placeholder="Search assets by domain, IP, or path..." 
          className="w-full bg-surface-solid border border-border-color rounded-lg pl-10 pr-4 py-3 text-white focus:border-primary focus:outline-none transition-colors"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {filteredAssets.length === 0 ? (
          <div className="col-span-full text-center py-16 text-text-muted bg-surface/50 rounded-xl border border-border-color border-dashed">
            <Server className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p className="text-lg">No assets discovered yet.</p>
            <p className="text-sm mt-1">Run a scan to populate this view.</p>
          </div>
        ) : (
          filteredAssets.map((a) => (
            <Card key={a.id} className="bg-surface/50 border-border-color hover:border-border-color-hover transition-colors overflow-hidden flex flex-col">
              <CardBody className="p-0 flex flex-col h-full">
                {/* Screenshot Area */}
                {a.metadata?.screenshot_path ? (
                  <div className="w-full border-b border-border-color bg-black/20">
                    <SecureImage url={`${BASE_URL}/workspaces/${id}/assets/${a.id}/screenshot`} />
                  </div>
                ) : (
                  <div className="h-2 bg-primary/20 w-full"></div>
                )}
                
                <div className="p-5 flex-1">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded bg-surface-solid text-text-secondary`}>
                        {a.asset_type === 'domain' || a.asset_type === 'url' ? <Globe className="w-5 h-5" /> : <Server className="w-5 h-5" />}
                      </div>
                      <h3 className="text-lg font-semibold text-white font-mono break-all">{a.value}</h3>
                    </div>
                    <Badge variant={a.asset_type === 'url' ? 'success' : 'primary'} className="uppercase text-[10px] tracking-wider">
                      {a.asset_type}
                    </Badge>
                  </div>
                  
                  {/* Metadata display logic from WorkspaceDetail */}
                  {a.metadata && Object.keys(a.metadata).length > 0 && (
                    <div className="mt-4 p-3 bg-surface-solid rounded-lg border border-border-color text-sm space-y-2">
                      {a.metadata.status_code && (
                        <div className="flex items-center gap-2">
                          <strong className="text-text-secondary w-20">Status:</strong>
                          <Badge variant={a.metadata.status_code < 300 ? 'success' : a.metadata.status_code < 400 ? 'warning' : 'danger'}>
                            {a.metadata.status_code}
                          </Badge>
                        </div>
                      )}
                      
                      {a.metadata.title && (
                        <div className="flex items-start gap-2">
                          <strong className="text-text-secondary w-20 shrink-0">Title:</strong>
                          <span className="text-text-primary line-clamp-2">{a.metadata.title}</span>
                        </div>
                      )}
                      
                      {/* Structured Tech */}
                      {a.metadata.structured_tech && (
                        <div className="mt-3 space-y-2 pt-3 border-t border-border-color">
                          {['cms', 'frameworks', 'languages', 'servers'].map(category => {
                            const items = a.metadata.structured_tech[category];
                            if (!items || items.length === 0) return null;
                            return (
                              <div key={category} className="flex flex-wrap items-center gap-2">
                                <strong className="text-text-secondary w-20 capitalize">{category}:</strong>
                                {items.map((tech: string, i: number) => (
                                  <span key={i} className="text-xs bg-surface border border-border-color px-2 py-1 rounded">
                                    {tech}
                                  </span>
                                ))}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div className="mt-4 pt-4 border-t border-border-color flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-muted uppercase tracking-wide">Discovered By</span>
                      <div className="flex gap-1">
                        {a.source_tools?.map((tool: string) => (
                          <span key={tool} className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded uppercase">
                            {tool}
                          </span>
                        ))}
                      </div>
                    </div>
                    <span className="text-xs text-text-secondary">
                      {new Date(a.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </CardBody>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};
