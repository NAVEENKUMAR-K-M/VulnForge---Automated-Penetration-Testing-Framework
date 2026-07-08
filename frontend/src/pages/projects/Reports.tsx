import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { FileText, Download } from 'lucide-react';
import { BASE_URL } from '../../api/client';

export const ProjectReports: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [isGenerating, setIsGenerating] = useState(false);
  const [format, setFormat] = useState('html');

  const handleGenerate = async () => {
    if (!id) return;
    setIsGenerating(true);
    
    try {
      const token = localStorage.getItem('token');
      // Create a hidden form or use fetch and Blob to trigger download
      const response = await fetch(`${BASE_URL}/workspaces/${id}/reports/generate?format=${format}`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      });
      
      if (!response.ok) throw new Error('Generation failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Determine extension based on format
      let ext = format;
      if (format === 'markdown') ext = 'md';
      a.download = `vulnforge-report-${id.substring(0, 8)}.${ext}`;
      
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      
    } catch (e) {
      console.error(e);
      alert('Failed to generate report.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-display font-bold text-white mb-2">Reports</h1>
          <p className="text-text-secondary">Generate professional security assessment reports for this workspace.</p>
        </div>
      </div>

      <Card className="bg-surface/50 border-border-color max-w-2xl">
        <CardHeader className="border-b border-border-color pb-4">
          <CardTitle className="text-xl font-display font-semibold text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" /> Generate New Report
          </CardTitle>
        </CardHeader>
        <CardBody className="p-6">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Report Format</label>
              <select 
                value={format} 
                onChange={(e) => setFormat(e.target.value)}
                className="w-full bg-surface-solid border border-border-color rounded-lg px-4 py-3 text-white focus:outline-none focus:border-primary transition-colors"
              >
                <option value="html">HTML (Interactive)</option>
                <option value="pdf">PDF (Print Ready)</option>
                <option value="markdown">Markdown (Github Flavored)</option>
                <option value="json">JSON (Raw Data)</option>
              </select>
            </div>
            
            <div className="bg-primary/10 border border-primary/20 rounded-lg p-4">
              <h4 className="text-primary font-medium text-sm mb-1">Included Sections:</h4>
              <ul className="text-xs text-text-secondary space-y-1 list-disc list-inside">
                <li>Executive Summary & High-level Statistics</li>
                <li>Discovered Assets (Domains, IPs, URLs)</li>
                <li>Identified Technologies (CMS, Frameworks, Languages, Servers)</li>
                <li>Open Ports and Services</li>
                <li>Vulnerability Findings (Severities, CVEs, Exploit Evidence)</li>
                <li>Captured Screenshots (Visual Evidence)</li>
              </ul>
            </div>
            
            <Button 
              variant="primary" 
              className="w-full flex justify-center items-center gap-2 py-3"
              onClick={handleGenerate}
              disabled={isGenerating}
            >
              {isGenerating ? (
                <>Generating...</>
              ) : (
                <><Download className="w-4 h-4" /> Generate & Download</>
              )}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
};
