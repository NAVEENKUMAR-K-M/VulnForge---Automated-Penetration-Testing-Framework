import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardBody } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { workspacesApi } from '../api/workspaces';
import type { Workspace } from '../api/workspaces';

export const Dashboard: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [totalTargets, setTotalTargets] = useState(0);
  const [totalVulns, setTotalVulns] = useState(0);
  const [activeScans, setActiveScans] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const wsData = await workspacesApi.list();
        setWorkspaces(wsData);

        // Fetch dashboard stats for all workspaces
        const statsPromises = wsData.map(ws => workspacesApi.getDashboard(ws.id).catch(() => null));
        const allStats = await Promise.all(statsPromises);
        
        let targetsCount = 0;
        let vulnsCount = 0;
        
        allStats.forEach(stat => {
          if (stat) {
            targetsCount += stat.targets_count || 0;
            vulnsCount += stat.open_vulnerabilities_count || 0;
          }
        });
        
        setTotalTargets(targetsCount);
        setTotalVulns(vulnsCount);
        // Active scans would ideally come from the stats too, but keeping 0 for now as scans aren't implemented
        setActiveScans(0);

      } catch (err) {
        console.error("Failed to load dashboard data", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  return (
    <div className="flex-col gap-6" style={{ height: '100%' }}>
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-secondary">Overview of all active penetration testing engagements.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
        <Card>
          <CardHeader>
            <CardTitle>Total Workspaces</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="text-3xl font-bold text-primary">
              {isLoading ? '...' : workspaces.length}
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Running Scans</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="flex-row items-center gap-3">
              <span className="text-3xl font-bold text-warning">{isLoading ? '...' : activeScans}</span>
              <Badge variant="warning">In Progress</Badge>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Critical Vulnerabilities</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="text-3xl font-bold text-danger">{isLoading ? '...' : totalVulns}</div>
          </CardBody>
        </Card>
      </div>
      
      <Card glass={false} style={{ flex: 1, minHeight: '300px' }}>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        <CardBody className="flex-col gap-4">
          <p className="text-secondary">No recent activity found in the logs.</p>
        </CardBody>
      </Card>
    </div>
  );
};
