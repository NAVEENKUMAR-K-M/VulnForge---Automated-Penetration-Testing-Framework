import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardBody } from '../../components/common/Card';
import { Activity, Server, Target, AlertTriangle } from 'lucide-react';
import { workspacesApi } from '../../api/workspaces';
import type { Workspace } from '../../api/workspaces';

export const ProjectDashboard: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);

  useEffect(() => {
    if (id) {
      workspacesApi.get(id).then(setWorkspace).catch(console.error);
    }
  }, [id]);

  if (!workspace) return <div className="text-text-secondary animate-pulse">Loading dashboard...</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-display font-bold text-white mb-2">{workspace.name} Dashboard</h1>
        <p className="text-text-secondary">{workspace.description || 'Overview of your security posture.'}</p>
      </div>

      {/* Tailwind Stat Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <Card className="bg-surface/50 border-border-color shadow-lg hover:shadow-primary/5 transition-all">
          <CardBody className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-secondary mb-1">Total Targets</p>
              <h3 className="text-3xl font-bold text-white">0</h3>
            </div>
            <div className="p-3 bg-primary/10 rounded-xl text-primary">
              <Target className="w-8 h-8" />
            </div>
          </CardBody>
        </Card>
        
        <Card className="bg-surface/50 border-border-color shadow-lg hover:shadow-primary/5 transition-all">
          <CardBody className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-secondary mb-1">Discovered Assets</p>
              <h3 className="text-3xl font-bold text-white">0</h3>
            </div>
            <div className="p-3 bg-blue-500/10 rounded-xl text-blue-500">
              <Server className="w-8 h-8" />
            </div>
          </CardBody>
        </Card>
        
        <Card className="bg-surface/50 border-border-color shadow-lg hover:shadow-danger/5 transition-all">
          <CardBody className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-secondary mb-1">Vulnerabilities</p>
              <h3 className="text-3xl font-bold text-white">0</h3>
            </div>
            <div className="p-3 bg-danger/10 rounded-xl text-danger">
              <AlertTriangle className="w-8 h-8" />
            </div>
          </CardBody>
        </Card>

        <Card className="bg-surface/50 border-border-color shadow-lg hover:shadow-success/5 transition-all">
          <CardBody className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-secondary mb-1">Active Scans</p>
              <h3 className="text-3xl font-bold text-white">0</h3>
            </div>
            <div className="p-3 bg-success/10 rounded-xl text-success">
              <Activity className="w-8 h-8" />
            </div>
          </CardBody>
        </Card>
      </div>
      
      {/* Recent Activity */}
      <Card className="bg-surface-solid border-border-color mt-8">
        <CardHeader className="border-b border-border-color pb-4">
          <CardTitle className="text-xl font-display font-semibold text-white">Recent Activity</CardTitle>
        </CardHeader>
        <CardBody className="p-6">
          <div className="text-center py-12 text-text-muted">
            <Activity className="w-12 h-12 mx-auto mb-3 opacity-20" />
            <p>No recent activity in this project.</p>
          </div>
        </CardBody>
      </Card>
    </div>
  );
};
