import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Crosshair, Play, StopCircle } from 'lucide-react';
// import { scansApi } from '../../api/scans'; // Assuming this exists or will be built

export const ProjectScans: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [scans, setScans] = useState<any[]>([]); // Mocking for now

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-display font-bold text-white mb-2">Scans</h1>
          <p className="text-text-secondary">Execute and monitor security scans against your targets.</p>
        </div>
        <Button variant="primary" className="flex items-center gap-2">
          <Play className="w-4 h-4" /> New Scan
        </Button>
      </div>

      <div className="grid gap-4">
        {scans.length === 0 ? (
          <div className="text-center py-16 text-text-muted bg-surface/50 rounded-xl border border-border-color border-dashed">
            <Crosshair className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p className="text-lg">No scans executed yet.</p>
            <p className="text-sm mt-1 text-text-secondary">Start a new scan to discover assets and vulnerabilities.</p>
          </div>
        ) : (
          scans.map((s, i) => (
            <Card key={i} className="bg-surface/50 border-border-color">
              <CardBody className="p-5 flex justify-between items-center">
                <div className="flex flex-col">
                  <h3 className="text-lg font-semibold text-white">{s.name || `Scan #${i+1}`}</h3>
                  <span className="text-sm text-text-secondary">Status: {s.status}</span>
                </div>
              </CardBody>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};
