/**
 * AlertRulesPanel - Manage alert rules (list / enable / delete / create) and control
 * the monitoring lifecycle (start / stop) for the selected datasource.
 */
import { useEffect, useState } from 'react';
import {
  alertRulesApi,
  type AlertRule,
  type AlertCondition,
} from '../api/alerts';

interface Props {
  /** Currently selected datasource id, used for monitoring start/stop. */
  dataSourceId?: string | null;
}

const SEVERITIES = ['P1', 'P2', 'P3'];
const OPERATORS = ['>', '>=', '<', '<=', '==', '!='];

const emptyRule = (): AlertRule => ({
  id: '',
  name: '',
  severity: 'P2',
  description: '',
  enabled: true,
  datasource_types: ['*'],
  conditions: [{ metric: '', operator: '>', threshold: 0, duration_minutes: 0 }],
  auto_resolve: true,
  cooldown_minutes: 15,
});

export function AlertRulesPanel({ dataSourceId }: Props) {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState<AlertRule>(emptyRule());

  const loadRules = async () => {
    setLoading(true);
    try {
      const res = await alertRulesApi.list();
      setRules(res.rules);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load rules');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  const toggleEnabled = async (rule: AlertRule) => {
    try {
      await alertRulesApi.update(rule.id, { ...rule, enabled: !rule.enabled });
      await loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update rule');
    }
  };

  const removeRule = async (rule: AlertRule) => {
    if (!confirm(`Delete alert rule "${rule.name}"?`)) return;
    try {
      await alertRulesApi.remove(rule.id);
      await loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule');
    }
  };

  const submitDraft = async () => {
    try {
      await alertRulesApi.create(draft);
      setShowForm(false);
      setDraft(emptyRule());
      await loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create rule');
    }
  };

  const updateCondition = (idx: number, patch: Partial<AlertCondition>) => {
    setDraft((d) => ({
      ...d,
      conditions: d.conditions.map((c, i) => (i === idx ? { ...c, ...patch } : c)),
    }));
  };

  const addCondition = () => {
    setDraft((d) => ({
      ...d,
      conditions: [...d.conditions, { metric: '', operator: '>', threshold: 0, duration_minutes: 0 }],
    }));
  };

  const removeCondition = (idx: number) => {
    setDraft((d) => ({
      ...d,
      // Keep at least one condition.
      conditions: d.conditions.length > 1 ? d.conditions.filter((_, i) => i !== idx) : d.conditions,
    }));
  };

  const monitoring = async (action: 'start' | 'stop') => {
    if (!dataSourceId) {
      setError('Select a datasource first to control monitoring.');
      return;
    }
    try {
      if (action === 'start') await alertRulesApi.startMonitoring(dataSourceId);
      else await alertRulesApi.stopMonitoring(dataSourceId);
      setInfo(`Monitoring ${action === 'start' ? 'started' : 'stopped'} for ${dataSourceId}`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} monitoring`);
    }
  };

  return (
    <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>⚙️ Alert Rules</h3>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={() => monitoring('start')} disabled={!dataSourceId} style={btnStyle('#10b981')}>
            ▶ Start Monitoring
          </button>
          <button onClick={() => monitoring('stop')} disabled={!dataSourceId} style={btnStyle('#ef4444')}>
            ⏹ Stop
          </button>
          <button onClick={() => setShowForm((s) => !s)} style={btnStyle('#3b82f6')}>
            {showForm ? 'Cancel' : '+ New Rule'}
          </button>
        </div>
      </div>

      {error && <Banner color="#ef4444" bg="#fee2e2">⚠️ {error}</Banner>}
      {info && <Banner color="#065f46" bg="#d1fae5">✓ {info}</Banner>}

      {showForm && (
        <div style={{ padding: '12px', border: '1px solid var(--border-color)', borderRadius: '6px', marginBottom: '12px' }}>
          <Field label="Rule ID">
            <input value={draft.id} onChange={(e) => setDraft({ ...draft, id: e.target.value })} style={inputStyle} placeholder="custom_cpu_high" />
          </Field>
          <Field label="Name">
            <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} style={inputStyle} />
          </Field>
          <Field label="Severity">
            <select value={draft.severity} onChange={(e) => setDraft({ ...draft, severity: e.target.value })} style={inputStyle}>
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Description">
            <input value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} style={inputStyle} />
          </Field>
          <Field label="Conditions (all must hold)">
            {draft.conditions.map((cond, idx) => (
              <div key={idx} style={{ display: 'flex', gap: '6px', marginBottom: '6px' }}>
                <input
                  placeholder="metric (e.g. cpu_percent)"
                  value={cond.metric}
                  onChange={(e) => updateCondition(idx, { metric: e.target.value })}
                  style={{ ...inputStyle, flex: 2 }}
                />
                <select value={cond.operator} onChange={(e) => updateCondition(idx, { operator: e.target.value })} style={{ ...inputStyle, flex: 1 }}>
                  {OPERATORS.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
                <input
                  type="number"
                  placeholder="threshold"
                  value={cond.threshold}
                  onChange={(e) => updateCondition(idx, { threshold: Number(e.target.value) })}
                  style={{ ...inputStyle, flex: 1 }}
                />
                <input
                  type="number"
                  title="Sustained minutes (0 = immediate)"
                  placeholder="min"
                  value={cond.duration_minutes ?? 0}
                  onChange={(e) => updateCondition(idx, { duration_minutes: Number(e.target.value) })}
                  style={{ ...inputStyle, flex: 1 }}
                />
                <button
                  type="button"
                  onClick={() => removeCondition(idx)}
                  disabled={draft.conditions.length <= 1}
                  style={{ ...btnStyle('#9ca3af'), padding: '6px 10px' }}
                >
                  ✕
                </button>
              </div>
            ))}
            <button type="button" onClick={addCondition} style={btnStyle('#6b7280')}>
              + Add condition
            </button>
          </Field>
          <Field label="Cooldown (min)">
            <input
              type="number"
              value={draft.cooldown_minutes}
              onChange={(e) => setDraft({ ...draft, cooldown_minutes: Number(e.target.value) })}
              style={inputStyle}
            />
          </Field>
          <button onClick={submitDraft} disabled={!draft.id || !draft.name} style={btnStyle('#3b82f6')}>
            Create Rule
          </button>
        </div>
      )}

      {loading ? (
        <p style={{ color: 'var(--text-secondary)' }}>Loading rules…</p>
      ) : rules.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>No alert rules defined.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {rules.map((rule) => (
            <div key={rule.id} style={{ padding: '10px 12px', border: '1px solid var(--border-color)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{ fontWeight: 600 }}>{rule.name}</span>{' '}
                  <span style={{ fontSize: '11px', padding: '1px 6px', borderRadius: '4px', backgroundColor: 'var(--bg-secondary)' }}>
                    {rule.severity}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button onClick={() => toggleEnabled(rule)} style={btnStyle(rule.enabled ? '#10b981' : '#9ca3af')}>
                    {rule.enabled ? 'Enabled' : 'Disabled'}
                  </button>
                  <button onClick={() => removeRule(rule)} style={btnStyle('#ef4444')}>Delete</button>
                </div>
              </div>
              <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>{rule.description}</p>
              <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {rule.conditions.map((c) => `${c.metric} ${c.operator} ${c.threshold}`).join(', ')}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function btnStyle(bg: string): React.CSSProperties {
  return {
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: 600,
    backgroundColor: bg,
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
  };
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '6px 8px',
  fontSize: '13px',
  border: '1px solid var(--border-color)',
  borderRadius: '4px',
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '8px' }}>
      <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: 'var(--text-secondary)' }}>{label}</label>
      {children}
    </div>
  );
}

function Banner({ color, bg, children }: { color: string; bg: string; children: React.ReactNode }) {
  return (
    <div style={{ padding: '10px 12px', marginBottom: '12px', backgroundColor: bg, color, borderRadius: '6px', fontSize: '13px' }}>
      {children}
    </div>
  );
}

export default AlertRulesPanel;
