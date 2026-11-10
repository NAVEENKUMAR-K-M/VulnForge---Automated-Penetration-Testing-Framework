import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Bot, Play, ShieldCheck, ShieldAlert, Check, X, RefreshCw } from 'lucide-react';
import { Card, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { agentApi } from '../../api/agent';
import type {
  AgentRunSummary,
  AgentRunDetail,
  AgentRunStatus,
  AgentActionState,
  ActionTier,
} from '../../api/agent';
import { targetsApi } from '../../api/targets';
import type { Target } from '../../api/targets';

const runStatusVariant: Record<AgentRunStatus, any> = {
  pending: 'secondary',
  running: 'primary',
  awaiting_approval: 'warning',
  completed: 'success',
  failed: 'danger',
  cancelled: 'secondary',
};

const stateVariant: Record<AgentActionState, any> = {
  proposed: 'warning',
  approved: 'primary',
  rejected: 'secondary',
  executed: 'success',
  failed: 'danger',
  skipped: 'secondary',
};

const tierVariant: Record<ActionTier, any> = { passive: 'secondary', active: 'danger' };

export const ProjectAgent: React.FC = () => {
  const { id: workspaceId } = useParams<{ id: string }>();
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [selected, setSelected] = useState<AgentRunDetail | null>(null);
  const [targetId, setTargetId] = useState('');
  const [objective, setObjective] = useState('');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    if (!workspaceId) return;
    try {
      setRuns(await agentApi.listRuns(workspaceId));
    } catch (e: any) {
      setError(e.message);
    }
  }, [workspaceId]);

  const loadRun = useCallback(
    async (runId: string) => {
      if (!workspaceId) return;
      try {
        setSelected(await agentApi.getRun(workspaceId, runId));
      } catch (e: any) {
        setError(e.message);
      }
    },
    [workspaceId]
  );

  useEffect(() => {
    loadRuns();
    if (workspaceId) targetsApi.list(workspaceId).then(setTargets).catch(() => {});
  }, [workspaceId, loadRuns]);

  // Auto-refresh the selected run while it is active.
  useEffect(() => {
    if (!selected) return;
    if (selected.status !== 'running' && selected.status !== 'awaiting_approval') return;
    const t = setInterval(() => {
      loadRun(selected.id);
      loadRuns();
    }, 4000);
    return () => clearInterval(t);
  }, [selected, loadRun, loadRuns]);

  const start = async () => {
    if (!workspaceId || !targetId) return;
    setStarting(true);
    setError(null);
    try {
      const run = await agentApi.startRun(workspaceId, {
        target_id: targetId,
        objective: objective || undefined,
      });
      setObjective('');
      await loadRuns();
      await loadRun(run.id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  const decide = async (actionId: string, approve: boolean) => {
    if (!workspaceId || !selected) return;
    try {
      const updated = approve
        ? await agentApi.approve(workspaceId, selected.id, actionId)
        : await agentApi.reject(workspaceId, selected.id, actionId);
      setSelected(updated);
      loadRuns();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-display font-bold text-white mb-2 flex items-center gap-3">
            <Bot className="w-8 h-8 text-primary" /> Agent
          </h1>
          <p className="text-text-secondary">
            Autonomous recon with human approval gates on every active action.
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-danger/10 border border-danger/40 text-danger rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* New run */}
      <Card className="bg-surface/50 border-border-color">
        <CardBody className="p-5 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-text-secondary">Target</label>
            <select
              className="bg-surface-solid border border-border-color rounded-md px-3 py-2 text-white min-w-[220px]"
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
            >
              <option value="">Select a target…</option>
              {targets.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.value})
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1 flex-1 min-w-[220px]">
            <label className="text-xs text-text-secondary">Objective (optional)</label>
            <input
              className="bg-surface-solid border border-border-color rounded-md px-3 py-2 text-white"
              placeholder="e.g. External assessment of the web app"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
            />
          </div>
          <Button
            variant="primary"
            isLoading={starting}
            disabled={!targetId}
            leftIcon={<Play className="w-4 h-4" />}
            onClick={start}
          >
            Start Run
          </Button>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Runs list */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Runs</h2>
            <button onClick={loadRuns} className="text-text-muted hover:text-white">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          {runs.length === 0 ? (
            <p className="text-text-muted text-sm">No agent runs yet.</p>
          ) : (
            runs.map((r) => (
              <button
                key={r.id}
                onClick={() => loadRun(r.id)}
                className={`w-full text-left rounded-lg border p-3 transition-colors ${
                  selected?.id === r.id
                    ? 'border-primary bg-primary/10'
                    : 'border-border-color bg-surface/50 hover:bg-surface-hover'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-white text-sm font-medium truncate">{r.name}</span>
                  <Badge variant={runStatusVariant[r.status]}>{r.status.replace('_', ' ')}</Badge>
                </div>
                <span className="text-xs text-text-muted">
                  {new Date(r.created_at).toLocaleString()}
                </span>
              </button>
            ))
          )}
        </div>

        {/* Run detail */}
        <div className="lg:col-span-2">
          {!selected ? (
            <div className="text-center py-16 text-text-muted bg-surface/50 rounded-xl border border-border-color border-dashed">
              <Bot className="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p>Select a run to view its actions, or start a new one.</p>
            </div>
          ) : (
            <Card className="bg-surface/50 border-border-color">
              <CardBody className="p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{selected.name}</h3>
                    {selected.objective && (
                      <p className="text-sm text-text-secondary">{selected.objective}</p>
                    )}
                  </div>
                  <Badge variant={runStatusVariant[selected.status]}>
                    {selected.status.replace('_', ' ')}
                  </Badge>
                </div>

                {selected.status === 'awaiting_approval' && (
                  <div className="bg-warning/10 border border-warning/40 text-warning rounded-lg px-4 py-2 text-sm flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4" />
                    This run is paused — approve or reject the proposed active action(s) below.
                  </div>
                )}

                <div className="space-y-2">
                  {selected.actions.map((a) => (
                    <div
                      key={a.id}
                      className="rounded-lg border border-border-color bg-surface-solid/60 p-3"
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2">
                          <span className="text-text-muted text-xs">#{a.step_index}</span>
                          {a.tier === 'active' ? (
                            <ShieldAlert className="w-4 h-4 text-danger" />
                          ) : (
                            <ShieldCheck className="w-4 h-4 text-text-muted" />
                          )}
                          <span className="text-white font-medium">{a.tool_name}</span>
                          <Badge variant={tierVariant[a.tier]}>{a.tier}</Badge>
                          <Badge variant={stateVariant[a.state]}>{a.state}</Badge>
                        </div>
                        {a.state === 'proposed' && (
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="primary"
                              leftIcon={<Check className="w-3 h-3" />}
                              onClick={() => decide(a.id, true)}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="danger"
                              leftIcon={<X className="w-3 h-3" />}
                              onClick={() => decide(a.id, false)}
                            >
                              Reject
                            </Button>
                          </div>
                        )}
                      </div>
                      {a.rationale && (
                        <p className="text-xs text-text-secondary mt-1">{a.rationale}</p>
                      )}
                      {(a.result_summary || a.error_message) && (
                        <p className="text-xs text-text-muted mt-1">
                          {a.result_summary || a.error_message}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
