/**
 * AgentPanel — Autonomous + manual DBA agent UI.
 *
 * Improvements in this version:
 *  - Rich approval cards: problem statement, SQL preview, derived rollback
 *    script, audit log trail, risk badge, submitted-by / timestamp
 *  - Live scan progress: per-DS step label updated every 2 s while scanning
 *  - Auto-mode toggle with interval picker and countdown
 *  - Multi-DB health cards grid
 */
import { useEffect, useRef, useState } from 'react';
import {
  ShieldAlert, Bot, Play, Check, X, RefreshCw, AlertTriangle,
  ChevronDown, ChevronUp, Clock, User, Database,
} from 'lucide-react';
import {
  agentApi, mcpApi, datasourcesApi,
  type DataSource, type AgentTraceStep, type DestructiveAlert,
  type ScanStatusResponse, type PerDsResultSummary, type AuditEntry,
} from '../api/client';
import { useLocalStorage } from '../hooks/useLocalStorage';

// ── Types ─────────────────────────────────────────────────────────────────────

type PendingRecord = {
  approval_id: string;
  status: string;
  ds_id?: string;
  submitted_at?: string;
  submitted_by?: string;
  approved_at?: string;
  approved_by?: string;
  rollback_sql?: string;
  rollback_available?: boolean;
  notes?: Array<{ timestamp: string; user: string; type: string; content: string }>;
  suggestion: {
    sql?: string;
    risk_class?: string;
    risk_level?: string;
    rationale?: string;
    category?: string;
    related_objects?: string[];
    tables_affected?: string[];
    [k: string]: any;
  };
};

// ── Constants ─────────────────────────────────────────────────────────────────

const RISK_BADGE: Record<string, string> = {
  metadata_read:  'bg-emerald-500/15 text-emerald-600 border-emerald-500/30',
  safe_write:     'bg-sky-500/15 text-sky-600 border-sky-500/30',
  impactful_write:'bg-amber-500/15 text-amber-600 border-amber-500/30',
  destructive:    'bg-red-500/15 text-red-600 border-red-500/30',
  unknown:        'bg-zinc-500/15 text-zinc-500 border-zinc-500/30',
};

const RISK_LABEL: Record<string, string> = {
  metadata_read:  'Read-only',
  safe_write:     'Safe write',
  impactful_write:'Impactful write',
  destructive:    'Destructive',
  unknown:        'Unknown',
};

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  ok:         { background: 'rgba(16,185,129,.12)', color: '#059669', border: '1px solid rgba(16,185,129,.3)' },
  approved:   { background: 'rgba(59,130,246,.12)', color: '#2563eb', border: '1px solid rgba(59,130,246,.3)' },
  blocked:    { background: 'rgba(239,68,68,.12)',  color: '#dc2626', border: '1px solid rgba(239,68,68,.3)' },
  error:      { background: 'rgba(239,68,68,.12)',  color: '#dc2626', border: '1px solid rgba(239,68,68,.3)' },
  no_finding: { background: 'rgba(113,113,122,.12)', color: '#71717a', border: '1px solid rgba(113,113,122,.3)' },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function targetObject(rec: PendingRecord): string {
  const s = rec.suggestion || {};
  if (s.related_objects?.length) return s.related_objects[0];
  if (s.tables_affected?.length) return s.tables_affected[0];
  const m =
    (s.sql || '').match(/\bON\s+([A-Za-z_][\w.]*)/i) ||
    (s.sql || '').match(/\b(?:TABLE|ANALYZE)\s+([A-Za-z_][\w.]*)/i);
  return m ? m[1] : 'CONFIRM';
}

/** Derive a rollback statement from a proposed SQL string. */
function deriveRollback(sql: string): string | null {
  const s = (sql || '').trim();
  const up = s.toUpperCase();
  if (up.startsWith('CREATE INDEX CONCURRENTLY') || up.startsWith('CREATE UNIQUE INDEX CONCURRENTLY')) {
    const m = s.match(/CREATE(?:\s+UNIQUE)?\s+INDEX\s+CONCURRENTLY\s+(?:IF\s+NOT\s+EXISTS\s+)?(\S+)/i);
    return m ? `DROP INDEX CONCURRENTLY IF EXISTS ${m[1]};` : null;
  }
  if (up.startsWith('CREATE UNIQUE INDEX')) {
    const m = s.match(/CREATE\s+UNIQUE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\S+)/i);
    return m ? `DROP INDEX IF EXISTS ${m[1]};` : null;
  }
  if (up.startsWith('CREATE INDEX')) {
    const m = s.match(/CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\S+)/i);
    return m ? `DROP INDEX IF EXISTS ${m[1]};` : null;
  }
  if (up.startsWith('ANALYZE ')) {
    return '-- ANALYZE is safe and idempotent; no rollback required.';
  }
  if (up.startsWith('SET ')) {
    const m = s.match(/SET\s+(\S+)\s*=/i);
    return m ? `RESET ${m[1]};` : null;
  }
  return null;
}

function relativeTime(iso: string | undefined): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ── Main component ────────────────────────────────────────────────────────────

export function AgentPanel() {
  // Single-datasource investigation (original)
  const [datasources, setDatasources] = useState<Record<string, DataSource>>({});
  const [dsId, setDsId] = useState('');
  const [goal, setGoal] = useState('find slow lookups and propose an index');
  const [maxIters, setMaxIters] = useState(8);

  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState<AgentTraceStep[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [pending, setPending] = useState<PendingRecord[]>([]);
  const [alerts, setAlerts] = useState<DestructiveAlert[]>([]);
  const [confirmText, setConfirmText] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  // Autonomous scan mode
  const [autoMode, setAutoMode] = useLocalStorage<boolean>('agent-auto-mode', false);
  const [scanInterval, setScanInterval] = useLocalStorage<number>('agent-scan-interval', 5);
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState<ScanStatusResponse | null>(null);
  const [allResults, setAllResults] = useState<PerDsResultSummary[]>([]);
  const [nextScanIn, setNextScanIn] = useState(0);
  const countdownRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Audit log tab
  const [activeTab, setActiveTab] = useState<'approvals' | 'audit'>('approvals');
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);

  // ── Mount ─────────────────────────────────────────────────────────────────
  useEffect(() => { loadDatasources(); }, []);
  useEffect(() => { if (dsId) refresh(); }, [dsId]);
  useEffect(() => {
    agentApi.getScanResults().then((r) => setAllResults(r.results)).catch(() => {});
  }, []);

  // ── Scan-status polling (every 2 s while scanning) ────────────────────────
  useInterval(async () => {
    try {
      const status = await agentApi.getScanStatus();
      setScanStatus(status);
      if (!status.scanning) {
        setScanning(false);
        const res = await agentApi.getScanResults();
        setAllResults(res.results);
        if (dsId) refresh();
      }
    } catch { /* silent */ }
  }, scanning ? 2000 : null);

  // ── Auto-mode countdown → trigger ─────────────────────────────────────────
  useEffect(() => {
    if (!autoMode || scanning) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }
    countdownRef.current = scanInterval * 60;
    setNextScanIn(countdownRef.current);
    timerRef.current = setInterval(() => {
      countdownRef.current -= 1;
      setNextScanIn(countdownRef.current);
      if (countdownRef.current <= 0) {
        clearInterval(timerRef.current!);
        runScanAll();
      }
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoMode, scanning, scanInterval]);

  // ── Data helpers ──────────────────────────────────────────────────────────
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

  async function loadAuditLog() {
    setAuditLoading(true);
    try {
      const res = await agentApi.getAuditLog(dsId || undefined, 200);
      setAuditLog(res.entries);
    } catch { /* silent */ }
    finally { setAuditLoading(false); }
  }

  // ── Actions ───────────────────────────────────────────────────────────────
  async function runScanAll() {
    if (scanning) return;
    setScanning(true); setError(null);
    try {
      await agentApi.scanAll({ max_iters_per_ds: 8, token_budget_per_ds: 8000 });
    } catch (e: any) {
      setError(e.message || 'Scan all failed');
      setScanning(false);
    }
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
      const res = await mcpApi.execute(dsId, rec.approval_id, 'user');
      setPending((prev) => prev.map((r) => r.approval_id === rec.approval_id ? { ...r, status: 'executed' } : r));
      setError(null);
      alert(`✅ Executed (dry-run validated first)\n\n${res.message}`);
    } catch (e: any) { setError(e.message || 'Execution failed (dry-run may have blocked it)'); }
    finally { setBusy((b) => ({ ...b, [rec.approval_id]: false })); }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex-1 overflow-auto bg-background p-6 space-y-6">

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10"><Bot className="h-5 w-5 text-primary" /></div>
        <div>
          <h2 className="text-lg font-semibold">Agentic DBA</h2>
          <p className="text-sm text-muted-foreground">
            Proactive scanning across all databases. Proposals are screened at the guardrail
            wall and require human approval before execution.
          </p>
        </div>
      </div>

      {/* ── Auto-mode control bar ── */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex items-center gap-4 flex-wrap">
          <button
            onClick={() => setAutoMode(!autoMode)}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
              autoMode ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'bg-muted text-foreground hover:bg-muted/80'
            }`}
          >
            {autoMode ? '🤖 Auto ON' : '⏸ Paused'}
          </button>

          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Every</span>
            <select
              value={scanInterval}
              onChange={(e) => setScanInterval(Number(e.target.value))}
              disabled={scanning}
              className="px-2 py-1 border border-border rounded bg-card text-sm"
            >
              {[1, 5, 15, 30, 60].map((m) => <option key={m} value={m}>{m} min</option>)}
            </select>
          </div>

          <button
            onClick={runScanAll}
            disabled={scanning}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
            data-testid="scan-all-btn"
          >
            {scanning ? '⏳ Scanning…' : '⚡ Scan All Now'}
          </button>

          {!scanning && autoMode && nextScanIn > 0 && (
            <span className="text-sm text-muted-foreground ml-auto">
              Next scan in {Math.floor(nextScanIn / 60)}:{String(nextScanIn % 60).padStart(2, '0')}
            </span>
          )}
        </div>

        {/* Live per-DS progress during scan */}
        {scanning && scanStatus && (
          <div className="border-t border-border pt-3 space-y-1.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Scan progress — {scanStatus.elapsed_s?.toFixed(0) ?? 0}s elapsed
            </p>
            {Object.entries(scanStatus.step_info || {}).map(([db, step]) => {
              const isDone = scanStatus.completed.includes(db);
              const isFailed = scanStatus.failed.includes(db);
              const isRunning = scanStatus.in_progress.includes(db);
              return (
                <div key={db} className="flex items-center gap-2 text-sm">
                  {isDone
                    ? <span className="text-emerald-500 font-bold">✓</span>
                    : isFailed
                    ? <span className="text-red-500 font-bold">✗</span>
                    : <span className="inline-block h-3 w-3 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                  }
                  <span className={`font-mono ${isDone ? 'text-muted-foreground' : isFailed ? 'text-red-600' : 'text-foreground'}`}>
                    {db}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {isRunning ? step : isDone ? 'complete' : step}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Per-DB health cards ── */}
      {allResults.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            All Databases — Latest Scan
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {allResults.map((r) => <DbStatusCard key={r.ds_id} result={r} />)}
          </div>
        </div>
      )}

      {/* ── Destructive-blocked banner ── */}
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

      {/* ── Manual investigation form ── */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Manual Investigation</p>
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

      {/* ── Step trace ── */}
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

      {/* ── Tab bar ── */}
      <div className="flex gap-1 border-b border-border">
        {(['approvals', 'audit'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => {
              setActiveTab(tab);
              if (tab === 'audit') loadAuditLog();
            }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab === 'approvals'
              ? `Pending Approvals (${pending.filter((p) => ['pending', 'approved'].includes(p.status)).length})`
              : 'Audit Log'}
          </button>
        ))}
      </div>

      {/* ── Pending approvals ── */}
      {activeTab === 'approvals' && (
        <div className="space-y-3">
          {pending.length === 0 && (
            <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
              No pending approvals. Run an investigation or use Scan All to generate remediation proposals.
            </div>
          )}
          {pending.map((rec) => (
            <ApprovalCard
              key={rec.approval_id}
              rec={rec}
              dsId={dsId}
              confirmText={confirmText}
              setConfirmText={setConfirmText}
              busy={!!busy[rec.approval_id]}
              onApprove={() => approve(rec)}
              onReject={() => reject(rec)}
              onExecute={() => execute(rec)}
            />
          ))}
        </div>
      )}

      {/* ── Audit log tab ── */}
      {activeTab === 'audit' && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              All agent actions, scans, investigations, and approval lifecycle events —
              newest first. Never deleted.
            </p>
            <button
              onClick={loadAuditLog}
              disabled={auditLoading}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              <RefreshCw className={`h-3 w-3 ${auditLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          {auditLog.length === 0 && !auditLoading && (
            <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
              No audit entries yet. Run a scan or investigation to generate events.
            </div>
          )}

          {auditLoading && (
            <div className="text-sm text-muted-foreground text-center py-6">Loading audit log…</div>
          )}

          <div className="space-y-1">
            {auditLog.map((entry) => (
              <AuditRow key={entry.id} entry={entry} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── ApprovalCard ──────────────────────────────────────────────────────────────

function ApprovalCard({
  rec, dsId, confirmText, setConfirmText, busy,
  onApprove, onReject, onExecute,
}: {
  rec: PendingRecord;
  dsId: string;
  confirmText: Record<string, string>;
  setConfirmText: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onExecute: () => void;
}) {
  const [showAudit, setShowAudit] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditEntry[] | null>(null);

  const rc = rec.suggestion?.risk_class || rec.suggestion?.risk_level || 'unknown';
  const sql = rec.suggestion?.sql || '';
  const rationale = rec.suggestion?.rationale || '';
  const category = rec.suggestion?.category || '';
  const rollback = rec.rollback_sql || deriveRollback(sql);

  const needsTyped = rc === 'impactful_write';
  const obj = targetObject(rec);
  const typedOk = !needsTyped || (confirmText[rec.approval_id]?.trim().toLowerCase() === obj.toLowerCase());

  async function loadAudit() {
    if (auditLog !== null) { setShowAudit(!showAudit); return; }
    try {
      const res = await agentApi.getApprovalAudit(dsId, rec.approval_id);
      setAuditLog(res.audit);
      setShowAudit(true);
    } catch {
      setAuditLog([]);
      setShowAudit(true);
    }
  }

  const statusColor = {
    pending: 'text-amber-600',
    approved: 'text-sky-600',
    executed: 'text-emerald-600',
    failed: 'text-red-600',
    rejected: 'text-zinc-400',
  }[rec.status] || 'text-muted-foreground';

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden" data-testid="approval-card">
      {/* Card header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-muted/30">
        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${RISK_BADGE[rc] || RISK_BADGE.unknown}`}>
          {RISK_LABEL[rc] || rc.replace('_', ' ')}
        </span>
        {category && (
          <span className="text-[10px] uppercase px-2 py-0.5 rounded border border-border text-muted-foreground">
            {category}
          </span>
        )}
        <span className={`text-[10px] uppercase font-semibold ml-1 ${statusColor}`}>{rec.status}</span>
        <span className="ml-auto text-[11px] text-muted-foreground flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {relativeTime(rec.submitted_at)}
          {rec.submitted_by && (
            <span className="flex items-center gap-0.5 ml-1">
              <User className="h-3 w-3" /> {rec.submitted_by}
            </span>
          )}
        </span>
      </div>

      <div className="p-4 space-y-4">
        {/* Problem statement */}
        {rationale && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
              Problem identified
            </p>
            <p className="text-sm text-foreground">{rationale}</p>
          </div>
        )}

        {/* Proposed fix SQL */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
            Proposed fix
          </p>
          <pre className="text-xs bg-zinc-900 text-emerald-300 rounded-md p-3 overflow-auto whitespace-pre-wrap font-mono">
            {sql || '(no SQL)'}
          </pre>
        </div>

        {/* Rollback script */}
        {rollback && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
              Rollback script
            </p>
            <pre className="text-xs bg-zinc-900 text-amber-300 rounded-md p-3 overflow-auto whitespace-pre-wrap font-mono">
              {rollback}
            </pre>
          </div>
        )}

        {/* Typed confirmation for impactful writes */}
        {rec.status === 'pending' && needsTyped && (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3">
            <label className="block text-xs text-amber-600 font-medium mb-1.5">
              Impactful change — type <code className="bg-amber-500/15 px-1 rounded font-bold">{obj}</code> to unlock approval:
            </label>
            <input
              type="text"
              value={confirmText[rec.approval_id] || ''}
              onChange={(e) => setConfirmText((c) => ({ ...c, [rec.approval_id]: e.target.value }))}
              placeholder={obj}
              className="w-full px-2 py-1.5 border border-amber-500/50 rounded bg-card text-sm"
              data-testid="typed-confirm"
            />
          </div>
        )}

        {/* Action buttons */}
        {rec.status === 'pending' && (
          <div className="flex gap-2">
            <button
              onClick={onApprove}
              disabled={!typedOk || busy}
              className="flex-1 px-3 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center justify-center gap-1.5"
              data-testid="approve-btn"
            >
              <Check className="h-3.5 w-3.5" /> Approve
            </button>
            <button
              onClick={onReject}
              disabled={busy}
              className="flex-1 px-3 py-2 text-xs font-semibold rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 inline-flex items-center justify-center gap-1.5"
            >
              <X className="h-3.5 w-3.5" /> Reject
            </button>
          </div>
        )}

        {rec.status === 'approved' && (
          <button
            onClick={onExecute}
            disabled={busy}
            className="w-full px-3 py-2 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 inline-flex items-center justify-center gap-1.5"
            data-testid="execute-btn"
          >
            <Play className="h-3.5 w-3.5" /> Execute (server dry-run first)
          </button>
        )}

        {rec.status === 'executed' && (
          <div className="flex items-center gap-2 text-sm text-emerald-600 font-medium">
            <Check className="h-4 w-4" /> Executed — dry-run validated before commit
            {rec.approved_at && <span className="text-xs text-muted-foreground ml-auto">{relativeTime(rec.approved_at)}</span>}
          </div>
        )}

        {/* Audit log toggle */}
        <button
          onClick={loadAudit}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {showAudit ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          Audit log
          <span className="font-mono text-[10px] opacity-60">#{rec.approval_id.slice(-8)}</span>
        </button>

        {showAudit && auditLog !== null && (
          <div className="border-t border-border pt-3">
            {auditLog.length === 0 ? (
              <p className="text-xs text-muted-foreground">No audit entries found.</p>
            ) : (
              <ol className="space-y-2">
                {auditLog.map((entry) => (
                  <li key={entry.id} className="flex gap-2 text-xs">
                    <span className="text-muted-foreground w-32 shrink-0 font-mono">
                      {new Date(entry.ts + (entry.ts.endsWith('Z') ? '' : 'Z')).toLocaleTimeString()}
                    </span>
                    <span className={`w-20 shrink-0 font-semibold ${
                      entry.action === 'approve' ? 'text-emerald-600'
                      : entry.action === 'reject' ? 'text-red-600'
                      : entry.action === 'executed' ? 'text-sky-600'
                      : 'text-muted-foreground'
                    }`}>{entry.action}</span>
                    {entry.actor && <span className="text-muted-foreground">{entry.actor}</span>}
                    {entry.detail && (
                      <span className="text-muted-foreground truncate">
                        {typeof entry.detail === 'object'
                          ? Object.entries(entry.detail).map(([k, v]) => `${k}: ${v}`).join(' · ')
                          : String(entry.detail)
                        }
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StepBadge({ action }: { action: string }) {
  const map: Record<string, string> = {
    tool:            'text-sky-600',
    propose_queued:  'text-emerald-600',
    propose_blocked: 'text-red-600',
    finish:          'text-muted-foreground',
    halt:            'text-amber-600',
    error:           'text-red-600',
  };
  return <span className={`w-32 shrink-0 ${map[action] || 'text-foreground'}`}>{action}</span>;
}

function DbStatusCard({ result }: { result: PerDsResultSummary }) {
  const statusStyle = STATUS_STYLE[result.status] || STATUS_STYLE.no_finding;
  const time = result.last_scanned_at
    ? new Date(result.last_scanned_at + (result.last_scanned_at.endsWith('Z') ? '' : 'Z')).toLocaleTimeString()
    : null;

  return (
    <div className="rounded-lg border border-border bg-card p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium truncate flex items-center gap-1.5" title={result.ds_id}>
          <Database className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          {result.ds_id}
        </span>
        <span
          className="text-[10px] font-bold uppercase px-2 py-0.5 rounded shrink-0"
          style={statusStyle}
        >
          {result.status.replace('_', ' ')}
        </span>
      </div>

      {result.top_finding && (
        <p className="text-xs text-muted-foreground line-clamp-2">{result.top_finding}</p>
      )}
      {result.error && (
        <p className="text-xs text-red-600 bg-red-500/10 rounded px-2 py-1 break-all">{result.error}</p>
      )}

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        {result.approval_count > 0 && (
          <span className="text-sky-600 font-medium">{result.approval_count} pending</span>
        )}
        {result.blocked_count > 0 && (
          <span className="text-red-600 font-medium">{result.blocked_count} blocked</span>
        )}
        {time && <span className="ml-auto">{time}</span>}
      </div>
    </div>
  );
}

// ── AuditRow ──────────────────────────────────────────────────────────────────

const ACTION_COLOR: Record<string, string> = {
  scan_started:     'text-sky-500',
  scan_completed:   'text-emerald-500',
  scan_failed:      'text-red-500',
  investigation_run:'text-violet-500',
  approve:          'text-emerald-600',
  reject:           'text-red-600',
  executed:         'text-sky-600',
  execute_failed:   'text-red-600',
  submit:           'text-amber-500',
};

function AuditRow({ entry }: { entry: AuditEntry }) {
  const color = ACTION_COLOR[entry.action] || 'text-muted-foreground';
  const ts = new Date(entry.ts + (entry.ts.endsWith('Z') ? '' : 'Z'));
  return (
    <div className="flex items-start gap-3 text-xs py-1.5 border-b border-border/50 last:border-0">
      <span className="text-muted-foreground w-32 shrink-0 font-mono tabular-nums">
        {ts.toLocaleDateString()} {ts.toLocaleTimeString()}
      </span>
      <span className={`w-36 shrink-0 font-semibold ${color}`}>{entry.action}</span>
      {entry.ds_id && (
        <span className="text-muted-foreground w-24 shrink-0 truncate font-mono" title={entry.ds_id}>
          {entry.ds_id}
        </span>
      )}
      {entry.actor && (
        <span className="text-muted-foreground w-16 shrink-0 truncate">{entry.actor}</span>
      )}
      {entry.detail && (
        <span className="text-muted-foreground break-all line-clamp-2 flex-1">
          {typeof entry.detail === 'object'
            ? Object.entries(entry.detail)
                .filter(([, v]) => v !== null && v !== undefined && v !== '')
                .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
                .join(' · ')
            : String(entry.detail)
          }
        </span>
      )}
      {entry.approval_id && !entry.detail && (
        <span className="text-muted-foreground font-mono">#{entry.approval_id.slice(-10)}</span>
      )}
    </div>
  );
}

// ── useInterval ───────────────────────────────────────────────────────────────

function useInterval(cb: () => void, delayMs: number | null) {
  const saved = useRef(cb);
  useEffect(() => { saved.current = cb; }, [cb]);
  useEffect(() => {
    if (delayMs === null) return;
    const id = setInterval(() => saved.current(), delayMs);
    return () => clearInterval(id);
  }, [delayMs]);
}
