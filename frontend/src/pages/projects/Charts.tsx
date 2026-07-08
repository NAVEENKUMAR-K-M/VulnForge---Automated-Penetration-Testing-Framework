import React from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardBody } from '../../components/common/Card';
import { BarChart3, PieChart, Activity } from 'lucide-react';

export const ProjectCharts: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  // In a real application, we would use Recharts or Chart.js here and fetch analytical data.
  // For now, this is a placeholder UI for the Charts page.
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-display font-bold text-white mb-2">Analytics & Charts</h1>
          <p className="text-text-secondary">Visualize your security posture and trends over time.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-surface/50 border-border-color">
          <CardHeader className="border-b border-border-color pb-4">
            <CardTitle className="text-xl font-display font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary" /> Vulnerability Severity Distribution
            </CardTitle>
          </CardHeader>
          <CardBody className="p-6 h-64 flex items-center justify-center">
            <div className="text-center text-text-muted">
              <p>Chart data loading...</p>
              <p className="text-xs mt-2">(Recharts integration pending)</p>
            </div>
          </CardBody>
        </Card>

        <Card className="bg-surface/50 border-border-color">
          <CardHeader className="border-b border-border-color pb-4">
            <CardTitle className="text-xl font-display font-semibold text-white flex items-center gap-2">
              <PieChart className="w-5 h-5 text-primary" /> Top Technologies Discovered
            </CardTitle>
          </CardHeader>
          <CardBody className="p-6 h-64 flex items-center justify-center">
            <div className="text-center text-text-muted">
              <p>Chart data loading...</p>
              <p className="text-xs mt-2">(Recharts integration pending)</p>
            </div>
          </CardBody>
        </Card>

        <Card className="bg-surface/50 border-border-color lg:col-span-2">
          <CardHeader className="border-b border-border-color pb-4">
            <CardTitle className="text-xl font-display font-semibold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-primary" /> Scan Activity Timeline
            </CardTitle>
          </CardHeader>
          <CardBody className="p-6 h-64 flex items-center justify-center">
            <div className="text-center text-text-muted">
              <p>Chart data loading...</p>
              <p className="text-xs mt-2">(Recharts integration pending)</p>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};
