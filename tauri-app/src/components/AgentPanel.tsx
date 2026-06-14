/**
 * AgentPanel — Stage 6 UI for the autonomous, metadata-only DBA agent.
 *
 * - Runs POST /agent/{ds}/investigate and renders the bounded step trace.
 * - Routes resulting PENDING approvals into an approve → execute flow.
 * - Requires TYPED CONFIRMATION (target object name) before approving an
 *   `impactful_write`.
 * - Shows a persistent red banner of DESTRUCTIVE_BLOCKED alarms (informational
 *   only — they were blocked at the guardrail wall and can never be approved).
 * - Execution always runs a server-side dry-run before the real commit, so no
 *   UI path can execute without a confirmed dry-run pass.
 */
import { useEffect, useState } from 'react';
import { ShieldAlert, Bot, Play, Check, X, RefreshCw, AlertTriangle } from 'lucide-react';
import {
  agentApi, mcpApi, datasourcesApi,
  type DataSource, type AgentTraceStep, type DestructiveAlert,
} from '../api/client';

type PendingRecord = {
  approval_id: string;
  status: string;
  suggestion: {
    sql?: string;
    risk_class?: string;
    rationale?: string;
    related_objects?: string[];
    tables_affected?: string[];
    [k: string]: any;
  };
};

const RISK_BADGE: Record<string, string> = {
  metadata_read: 'bg-emerald-500/15 text-emerald-600 border-emerald-500/30',
  safe_write: 'bg-sky-500/15 text-sky-600 border-sky-500/30',
  impactful_write: 'bg-amber-500/15 text-amber-600 border-amber-500/30',
  destructive: 'bg-red-500/15 text-red-600 border-red-500/30',
  unknown: 'bg-zinc-500/15 text-zinc-500 border-zinc-500/30',
};

function targetObject(rec: PendingRecord): string {
  const s = rec.suggestion || {};
  if (s.related_objects?.length) return s.related_objects[0];
  if (s.tables_affected?.length) return s.tables_affected[0];
  const m = (s.sql || '').match(/\bON\s+([A-Za-z_][\w.]*)/i) || (s.sql || '').match(/\b(?:TABLE|ANALYZE)\s+([A-Za-z_][\w.]*)/i);
  return m ? m[1] : 'CONFIRM';
}

export function AgentPanel() {
  const [datasources, setDatasources] = useState<Record<string, DataSource>>({});
  const [dsId, setDsId] = useState('');
  const [goal, setGoal] = useState('find slow lookups and propose an index');
  const [maxIters, setMaxIters] = useState(6);

  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState<AgentTraceStep[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [pending, setPending] = useState<PendingRecord[]>([]);
  const [alerts, setAlerts] = useState<DestructiveAlert[]>([]);
  const [confirmText, setConfirmText] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  useEffect(() => { loadDatasources(); }, []);
  useEffect(() => { if (dsId) refresh(); }, [dsId]);

  async function loadDatasources() {
    try {
      const data = await datasourcesApi.list();
      setDatasources(data);
      const first = Object.keys(data)[0];
      if (first && !dsId) setDsId(first);
    } catch (e: any) { setError(e.message || 'Failed to load datasources'); }
  }

  async function refresh() {
    if (!dsId) return;
    try {
      const [p, a] = await Promise.all([
        mcpApi.getPending(dsId),
        agentApi.getDestructiveAlerts(dsId),
      ]);
      setPending((p.pending as PendingRecord[]) || []);
      setAlerts(a.alerts || []);
    } catch (e: any) { setError(e.message || 'Failed to refresh'); }
  }

  async function runInvestigation() {
    if (!dsId) { setError('Select a datasource first'); return; }
    setRunning(true); setError(null); setTrace(null);
    try {
      const res = await agentApi.investigate(dsId, { goal, max_iters: maxIters });
      setTrace(res.trace);
      await refresh();
    } catch (e: any) {
      setError(e.message || 'Investigation failed');
    } finally { setRunning(false); }
  }

  async function approve(rec: PendingRecord) {
    setBusy((b) => ({ ...b, [rec.approval_id]: true }));
    try {
      await mcpApi.approve(dsId, rec.approval_id, { notes: 'Approved via Agent panel' }, 'user');
      setPending((prev) => prev.map((r) => r.approval_id === rec.approval_id ? { ...r, status: 'approved' } : r));
    } catch (e: any) { setError(e.message || 'Approve failed'); }
    finally { setBusy((b) => ({ ...b, [rec.approval_id]: false })); }
  }

  async function reject(rec: PendingRecord) {
    setBusy((b) => ({ ...b, [rec.approval_id]: true }));
    try {
      await mcpApi.reject(dsId, rec.approval_id, { reason: 'Rejected via Agent panel' }, 'user');
      setPending((prev) => prev.filter((r) => r.approval_id !== rec.approval_id));
    } catch (e: any) { setError(e.message || 'Reject failed'); }
    finally { setBusy((b) => ({ ...b, [rec.approval_id]: false })); }
  }

  async function execute(rec: PendingRecord) {
    setBusy((b) => ({ ...b, [rec.approval_id]: true }));
    try {
      // Server runs a dry-run (BEGIN…ROLLBACK) before the real commit.
      const res = await mcpApi.execute(dsId, rec.approval_id, 'user');
      setPending((prev) => prev.map((r) => r.approval_id === rec.approval_id ? { ...r, status: 'executed' } : r));
      setError(null);
      alert(`✅ Executed (dry-run validated first)\n\n${res.message}`);
    } catch (e: any) { setError(e.message || 'Execution failed (dry-run may have blocked it)'); }
    finally { setBusy((b) => ({ ...b, [rec.approval_id]: false })); }
  }

  return (
    <div className="flex-1 overflow-auto bg-background p-6 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10"><Bot className="h-5 w-5 text-primary" /></div>
        <div>
          <h2 className="text-lg font-semibold">Agentic DBA</h2>
          <p className="text-sm text-muted-foreground">
            Bounded, metadata-only investigation. Proposals are screened at the guardrail wall and
            routed to human approval — nothing is auto-executed, and destructive statements are blocked.
          </p>
        </div>
      </div>

      {/* Destructive-blocked banner (persistent, non-approvable) */}
      {alerts.length > 0 && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4" data-testid="destructive-banner">
          <div className="flex items-center gap-2 font-semibold text-red-600">
            <ShieldAlert className="h-5 w-5" />
            {alerts.length} destructive statement{alerts.length > 1 ? 's' : ''} blocked at the guardrail wall
          </div>
          <p className="text-xs text-red-600/80 mt-1">
            These were rejected and <strong>cannot be approved or executed</strong>. Informational only.
          </p>
          <ul className="mt-2 space-y-1">
            {alerts.slice(0, 6).map((a) => (
              <li key={a.id} className="text-xs font-mono text-red-700 bg-red-500/5 rounded px-2 py-1">
                <span className="font-semibold">{a.matched_rule}</span> · via {a.source} — {a.statement}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Datasource + investigate form */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex items-center gap-3">
          <select
            value={dsId}
            onChange={(e) => setDsId(e.target.value)}
            className="px-3 py-2 border border-border rounded-lg bg-card text-foreground text-sm"
            data-testid="agent-ds-select"
          >
            <option value="">Select datasource…</option>
            {Object.entries(datasources).map(([id, ds]) => (
              <option key={id} value={id}>{id} ({ds.engine})</option>
            ))}
          </select>
          <button onClick={refresh} className="p-2 rounded-lg border border-border hover:bg-muted" title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
        <input
          type="text"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Investigation goal…"
          className="w-full px-3 py-2 border border-border rounded-lg bg-card text-foreground text-sm"
          data-testid="agent-goal"
        />
        <div className="flex items-center gap-3">
          <label className="text-xs text-muted-foreground">Max iterations</label>
          <input
            type="number" min={1} max={20} value={maxIters}
            onChange={(e) => setMaxIters(Number(e.target.value))}
            className="w-20 px-2 py-1 border border-border rounded bg-card text-sm"
          />
          <button
            onClick={runInvestigation}
            disabled={running || !dsId}
            className="ml-auto px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
            data-testid="agent-run"
          >
            {running ? '⏳ Investigating…' : '🔍 Run Investigation'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 text-red-600 border border-red-500/30 px-4 py-3 text-sm flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* Step trace */}
      {trace && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-2">Investigation trace ({trace.length} steps)</h3>
          <ol className="space-y-1">
            {trace.map((s, i) => (
              <li key={i} className="text-xs font-mono flex gap-2">
                <span className="text-muted-foreground w-6 shrink-0">{s.step ?? i + 1}</span>
                <StepBadge action={s.action} />
                <span className="text-foreground/90 break-all">
                  {s.tool || s.sql || s.summary || s.reason || s.detail || ''}
                  {s.approval_id ? ` → queued ${s.approval_id.slice(0, 18)}` : ''}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Pending approvals */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Pending approvals ({pending.filter(p => p.status === 'pending' || p.status === 'approved').length})</h3>
        </div>
        {pending.length === 0 && (
          <p className="text-sm text-muted-foreground">No pending approvals. Run an investigation to generate remediation proposals.</p>
        )}
        <div className="space-y-3">
          {pending.map((rec) => {
            const rc = rec.suggestion?.risk_class || 'unknown';
            const needsTyped = rc === 'impactful_write';
            const obj = targetObject(rec);
            const typedOk = !needsTyped || (confirmText[rec.approval_id]?.trim().toLowerCase() === obj.toLowerCase());
            const isBusy = !!busy[rec.approval_id];
            return (
              <div key={rec.approval_id} className="rounded-md border border-border p-3" data-testid="approval-card">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${RISK_BADGE[rc] || RISK_BADGE.unknown}`}>
                    {rc.replace('_', ' ')}
                  </span>
                  <span className="text-[10px] text-muted-foreground uppercase">{rec.status}</span>
                </div>
                <pre className="text-xs bg-zinc-900 text-zinc-100 rounded p-2 overflow-auto mb-2">{rec.suggestion?.sql}</pre>
                {rec.suggestion?.rationale && (
                  <p className="text-xs text-muted-foreground mb-2"><strong>Why:</strong> {rec.suggestion.rationale}</p>
                )}

                {rec.status === 'pending' && (
                  <>
                    {needsTyped && (
                      <div className="mb-2">
                        <label className="block text-xs text-amber-600 mb-1">
                          Impactful change — type <code className="font-semibold">{obj}</code> to enable approval:
                        </label>
                        <input
                          type="text"
                          value={confirmText[rec.approval_id] || ''}
                          onChange={(e) => setConfirmText((c) => ({ ...c, [rec.approval_id]: e.target.value }))}
                          placeholder={obj}
                          className="w-full px-2 py-1 border border-amber-500/50 rounded bg-card text-sm"
                          data-testid="typed-confirm"
                        />
                      </div>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={() => approve(rec)}
                        disabled={!typedOk || isBusy}
                        className="flex-1 px-3 py-1.5 text-xs font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center justify-center gap-1"
                        data-testid="approve-btn"
                      >
                        <Check className="h-3.5 w-3.5" /> Approve
                      </button>
                      <button
                        onClick={() => reject(rec)}
                        disabled={isBusy}
                        className="flex-1 px-3 py-1.5 text-xs font-medium rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 inline-flex items-center justify-center gap-1"
                      >
                        <X className="h-3.5 w-3.5" /> Reject
                      </button>
                    </div>
                  </>
                )}

                {rec.status === 'approved' && (
                  <button
                    onClick={() => execute(rec)}
                    disabled={isBusy}
                    className="w-full px-3 py-1.5 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 inline-flex items-center justify-center gap-1"
                    data-testid="execute-btn"
                  >
                    <Play className="h-3.5 w-3.5" /> Execute (server dry-run first)
                  </button>
                )}

                {rec.status === 'executed' && (
                  <div className="text-xs text-emerald-600 font-medium">✅ Executed (dry-run validated)</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StepBadge({ action }: { action: string }) {
  const map: Record<string, string> = {
    tool: 'text-sky-600',
    propose_queued: 'text-emerald-600',
    propose_blocked: 'text-red-600',
    finish: 'text-muted-foreground',
    halt: 'text-amber-600',
    error: 'text-red-600',
  };
  return <span className={`w-32 shrink-0 ${map[action] || 'text-foreground'}`}>{action}</span>;
}
