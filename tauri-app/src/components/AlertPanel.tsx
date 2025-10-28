/**
 * AlertPanel Component - Three-Tab Alert System
 *
 * Features:
 * - TAB 1 (Current): Active and acknowledged alerts
 * - TAB 2 (Resolved): Resolved alerts with automatic/manual tags
 * - TAB 3 (All): Complete alert history with summary
 * - Auto-refresh every 10 seconds
 * - Acknowledge and resolve alerts
 * - AI-powered alert analysis
 */

import { useState, useEffect } from 'react';

// ============================================================================
// Types
// ============================================================================

type TabType = 'current' | 'resolved' | 'all';

interface Alert {
  id: string;
  rule_id: string;
  severity: 'P1' | 'P2' | 'P3';
  title: string;
  message: string;
  datasource_id: string;
  datasource_engine: string;
  triggered_at: string;
  status: 'active' | 'acknowledged' | 'resolved' | 'auto_resolved';
  metric_value?: any;
  threshold?: any;
  metadata?: Record<string, any>;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  auto_resolved: boolean;
  resolution_type?: 'automatic' | 'manual' | null;
}

interface AlertAnalysis {
  alert_id: string;
  analyzed_at: string;
  root_cause: string;
  confidence: number;
  immediate_actions: string[];
  recommendations: Array<{
    type: 'config' | 'index' | 'query' | 'action' | 'note';
    summary: string;
    rationale: string;
    sql?: string;
    command?: string;
    risk_level: 'low' | 'medium' | 'high';
    expected_improvement?: string;
    priority: number;
  }>;
  estimated_resolution_time?: string;
}

interface Summary {
  active: number;
  acknowledged: number;
  resolved: number;
  auto_resolved: number;
}

// ============================================================================
// AlertPanel Component
// ============================================================================

const API_BASE = 'http://127.0.0.1:8095';

export default function AlertPanel() {
  const [activeTab, setActiveTab] = useState<TabType>('current');
  const [currentAlerts, setCurrentAlerts] = useState<Alert[]>([]);
  const [resolvedAlerts, setResolvedAlerts] = useState<Alert[]>([]);
  const [allAlerts, setAllAlerts] = useState<Alert[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [analysis, setAnalysis] = useState<AlertAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Fetch alerts based on active tab
  const fetchAlerts = async () => {
    setLoading(true);
    try {
      if (activeTab === 'current') {
        const response = await fetch(`${API_BASE}/alerts/active`);
        const data = await response.json();
        setCurrentAlerts(data.alerts || []);
      } else if (activeTab === 'resolved') {
        const response = await fetch(`${API_BASE}/alerts/resolved?limit=50`);
        const data = await response.json();
        setResolvedAlerts(data.alerts || []);
      } else if (activeTab === 'all') {
        const response = await fetch(`${API_BASE}/alerts/all?limit=100`);
        const data = await response.json();
        setAllAlerts(data.alerts || []);
        if (data.summary) {
          setSummary(data.summary);
        }
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch AI analysis for an alert
  const fetchAnalysis = async (alertId: string) => {
    setAnalysisLoading(true);
    try {
      const encodedId = encodeURIComponent(alertId);
      const response = await fetch(`${API_BASE}/alerts/${encodedId}/analyze`, {
        method: 'POST',
      });
      const data = await response.json();
      setAnalysis(data);
    } catch (error) {
      console.error('Failed to fetch analysis:', error);
    } finally {
      setAnalysisLoading(false);
    }
  };

  // Acknowledge an alert
  const acknowledgeAlert = async (alertId: string) => {
    try {
      const encodedId = encodeURIComponent(alertId);
      await fetch(`${API_BASE}/alerts/${encodedId}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          acknowledged_by: 'UI-Admin',
          notes: 'Acknowledged from UI',
        }),
      });
      fetchAlerts(); // Refresh
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    }
  };

  // Resolve an alert
  const resolveAlert = async (alertId: string) => {
    try {
      const encodedId = encodeURIComponent(alertId);
      await fetch(`${API_BASE}/alerts/${encodedId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resolved_by: 'UI-Admin',
          notes: 'Resolved from UI',
        }),
      });
      fetchAlerts(); // Refresh
      setSelectedAlert(null);
      setAnalysis(null);
    } catch (error) {
      console.error('Failed to resolve alert:', error);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchAlerts();
  }, [activeTab]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchAlerts();
    }, 10000); // 10 seconds

    return () => clearInterval(interval);
  }, [autoRefresh, activeTab]);

  const handleAlertClick = (alert: Alert) => {
    setSelectedAlert(alert);
    setAnalysis(null);
    fetchAnalysis(alert.id);
  };

  // Get alerts for current tab
  const getAlertsForTab = (): Alert[] => {
    if (activeTab === 'current') return currentAlerts;
    if (activeTab === 'resolved') return resolvedAlerts;
    return allAlerts;
  };

  // Group alerts by severity
  const alerts = getAlertsForTab();
  const groupedAlerts = {
    P1: alerts.filter((a) => a.severity === 'P1'),
    P2: alerts.filter((a) => a.severity === 'P2'),
    P3: alerts.filter((a) => a.severity === 'P3'),
  };

  return (
    <div style={styles.container}>
      {/* Header with Tabs */}
      <div style={styles.header}>
        <div style={styles.tabContainer}>
          <button
            onClick={() => setActiveTab('current')}
            style={{
              ...styles.tab,
              ...(activeTab === 'current' ? styles.activeTab : {}),
            }}
          >
            📋 Current
          </button>
          <button
            onClick={() => setActiveTab('resolved')}
            style={{
              ...styles.tab,
              ...(activeTab === 'resolved' ? styles.activeTab : {}),
            }}
          >
            ✅ Resolved
          </button>
          <button
            onClick={() => setActiveTab('all')}
            style={{
              ...styles.tab,
              ...(activeTab === 'all' ? styles.activeTab : {}),
            }}
          >
            📊 All
          </button>
        </div>

        <div style={styles.headerControls}>
          <label style={styles.autoRefreshLabel}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            {' '}Auto-refresh (10s)
          </label>
          <button onClick={fetchAlerts} style={styles.refreshButton}>
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Summary (All tab only) */}
      {activeTab === 'all' && summary && (
        <div style={styles.summary}>
          <div style={styles.summaryItem}>
            <span style={styles.summaryLabel}>Active:</span>
            <span style={styles.summaryValue}>{summary.active}</span>
          </div>
          <div style={styles.summaryItem}>
            <span style={styles.summaryLabel}>Acknowledged:</span>
            <span style={styles.summaryValue}>{summary.acknowledged}</span>
          </div>
          <div style={styles.summaryItem}>
            <span style={styles.summaryLabel}>Resolved:</span>
            <span style={styles.summaryValue}>{summary.resolved}</span>
          </div>
          <div style={styles.summaryItem}>
            <span style={styles.summaryLabel}>Auto-Resolved:</span>
            <span style={styles.summaryValue}>{summary.auto_resolved}</span>
          </div>
          <div style={styles.summaryItem}>
            <span style={styles.summaryLabel}>Total:</span>
            <span style={{ ...styles.summaryValue, fontWeight: 'bold' }}>
              {summary.active + summary.acknowledged + summary.resolved + summary.auto_resolved}
            </span>
          </div>
        </div>
      )}

      {loading ? (
        <div style={styles.loading}>Loading alerts...</div>
      ) : (
        <div style={styles.content}>
          {/* Alert List */}
          <div style={styles.alertList}>
            {alerts.length === 0 ? (
              <div style={styles.noAlerts}>
                {activeTab === 'current'
                  ? '✅ No active alerts - All systems operational'
                  : activeTab === 'resolved'
                  ? '📭 No resolved alerts yet'
                  : '📭 No alerts in system'}
              </div>
            ) : (
              <>
                {/* P1 Critical Alerts */}
                {groupedAlerts.P1.length > 0 && (
                  <div style={styles.severityGroup}>
                    <h3 style={{ ...styles.severityHeader, ...styles.p1Color }}>
                      🚨 P1 Critical ({groupedAlerts.P1.length})
                    </h3>
                    {groupedAlerts.P1.map((alert) => (
                      <AlertCard
                        key={alert.id}
                        alert={alert}
                        isSelected={selectedAlert?.id === alert.id}
                        onClick={() => handleAlertClick(alert)}
                        onAcknowledge={() => acknowledgeAlert(alert.id)}
                        onResolve={() => resolveAlert(alert.id)}
                        showResolutionTag={activeTab !== 'current'}
                      />
                    ))}
                  </div>
                )}

                {/* P2 High Priority Alerts */}
                {groupedAlerts.P2.length > 0 && (
                  <div style={styles.severityGroup}>
                    <h3 style={{ ...styles.severityHeader, ...styles.p2Color }}>
                      ⚠️ P2 High ({groupedAlerts.P2.length})
                    </h3>
                    {groupedAlerts.P2.map((alert) => (
                      <AlertCard
                        key={alert.id}
                        alert={alert}
                        isSelected={selectedAlert?.id === alert.id}
                        onClick={() => handleAlertClick(alert)}
                        onAcknowledge={() => acknowledgeAlert(alert.id)}
                        onResolve={() => resolveAlert(alert.id)}
                        showResolutionTag={activeTab !== 'current'}
                      />
                    ))}
                  </div>
                )}

                {/* P3 Medium Priority Alerts */}
                {groupedAlerts.P3.length > 0 && (
                  <div style={styles.severityGroup}>
                    <h3 style={{ ...styles.severityHeader, ...styles.p3Color }}>
                      ℹ️ P3 Medium ({groupedAlerts.P3.length})
                    </h3>
                    {groupedAlerts.P3.map((alert) => (
                      <AlertCard
                        key={alert.id}
                        alert={alert}
                        isSelected={selectedAlert?.id === alert.id}
                        onClick={() => handleAlertClick(alert)}
                        onAcknowledge={() => acknowledgeAlert(alert.id)}
                        onResolve={() => resolveAlert(alert.id)}
                        showResolutionTag={activeTab !== 'current'}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Alert Details Panel */}
          {selectedAlert && (
            <div style={styles.detailsPanel}>
              <h3 style={styles.detailsTitle}>{selectedAlert.title}</h3>
              <div style={styles.detailsContent}>
                <p>
                  <strong>Severity:</strong>{' '}
                  <span
                    style={
                      selectedAlert.severity === 'P1'
                        ? styles.p1Color
                        : selectedAlert.severity === 'P2'
                        ? styles.p2Color
                        : styles.p3Color
                    }
                  >
                    {selectedAlert.severity}
                  </span>
                </p>
                <p>
                  <strong>Status:</strong> {selectedAlert.status}
                </p>
                {selectedAlert.resolution_type && (
                  <p>
                    <strong>Resolution Type:</strong>{' '}
                    <span
                      style={{
                        ...styles.resolutionBadge,
                        backgroundColor:
                          selectedAlert.resolution_type === 'automatic' ? '#059669' : '#0891b2',
                      }}
                    >
                      {selectedAlert.resolution_type === 'automatic' ? '[AUTO]' : '[MANUAL]'}{' '}
                      {selectedAlert.resolution_type.toUpperCase()}
                    </span>
                  </p>
                )}
                <p>
                  <strong>Database:</strong> {selectedAlert.datasource_id} (
                  {selectedAlert.datasource_engine})
                </p>
                <p>
                  <strong>Triggered:</strong>{' '}
                  {new Date(selectedAlert.triggered_at).toLocaleString()}
                </p>
                {selectedAlert.resolved_at && (
                  <p>
                    <strong>Resolved:</strong>{' '}
                    {new Date(selectedAlert.resolved_at).toLocaleString()}
                  </p>
                )}
                <p>
                  <strong>Message:</strong> {selectedAlert.message}
                </p>
                {selectedAlert.metric_value !== undefined && (
                  <p>
                    <strong>Metric:</strong> {selectedAlert.metric_value} (threshold:{' '}
                    {selectedAlert.threshold})
                  </p>
                )}

                {/* AI Analysis */}
                <div style={styles.analysisSection}>
                  <h4>🤖 AI Analysis & Recommendations</h4>
                  {analysisLoading ? (
                    <div style={styles.analysisLoading}>Analyzing alert with AI...</div>
                  ) : analysis ? (
                    <>
                      <div style={styles.rootCause}>
                        <strong>Root Cause:</strong> {analysis.root_cause}
                        <br />
                        <small style={styles.confidence}>
                          Confidence: {(analysis.confidence * 100).toFixed(0)}%
                        </small>
                      </div>

                      <div style={styles.immediateActions}>
                        <strong>Immediate Actions:</strong>
                        <ul>
                          {analysis.immediate_actions.map((action, idx) => (
                            <li key={idx}>{action}</li>
                          ))}
                        </ul>
                      </div>

                      <div style={styles.recommendations}>
                        <strong>Recommendations:</strong>
                        {analysis.recommendations.map((rec, idx) => (
                          <div key={idx} style={styles.recommendation}>
                            <div style={styles.recHeader}>
                              <span style={styles.recType}>{rec.type.toUpperCase()}</span>
                              <span
                                style={{
                                  ...styles.riskBadge,
                                  backgroundColor:
                                    rec.risk_level === 'high'
                                      ? '#dc3545'
                                      : rec.risk_level === 'medium'
                                      ? '#ffc107'
                                      : '#28a745',
                                }}
                              >
                                {rec.risk_level} risk
                              </span>
                            </div>
                            <p>
                              <strong>{rec.summary}</strong>
                            </p>
                            <p style={styles.rationale}>{rec.rationale}</p>
                            {rec.sql && <pre style={styles.codeBlock}>{rec.sql}</pre>}
                            {rec.command && <pre style={styles.codeBlock}>{rec.command}</pre>}
                            {rec.expected_improvement && (
                              <p style={styles.improvement}>
                                📈 Expected: {rec.expected_improvement}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>

                      {analysis.estimated_resolution_time && (
                        <p style={styles.eta}>
                          ⏱️ Estimated Resolution Time: {analysis.estimated_resolution_time}
                        </p>
                      )}
                    </>
                  ) : (
                    <div>Click an alert to see AI analysis</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// AlertCard Subcomponent
// ============================================================================

interface AlertCardProps {
  alert: Alert;
  isSelected: boolean;
  onClick: () => void;
  onAcknowledge: () => void;
  onResolve: () => void;
  showResolutionTag: boolean;
}

function AlertCard({
  alert,
  isSelected,
  onClick,
  onAcknowledge,
  onResolve,
  showResolutionTag,
}: AlertCardProps) {
  const severityColor =
    alert.severity === 'P1'
      ? '#dc3545'
      : alert.severity === 'P2'
      ? '#ffc107'
      : '#17a2b8';

  return (
    <div
      style={{
        ...styles.alertCard,
        borderLeft: `4px solid ${severityColor}`,
        backgroundColor: isSelected ? 'var(--muted)' : 'var(--card)',
      }}
      onClick={onClick}
    >
      <div style={styles.alertCardHeader}>
        <strong style={{ color: severityColor }}>{alert.title}</strong>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {showResolutionTag && alert.resolution_type && (
            <span
              style={{
                ...styles.resolutionBadge,
                backgroundColor:
                  alert.resolution_type === 'automatic' ? '#059669' : '#0891b2',
              }}
            >
              {alert.resolution_type === 'automatic' ? '[AUTO]' : '[MANUAL]'}
            </span>
          )}
          <span style={styles.alertTime}>
            {new Date(alert.triggered_at).toLocaleTimeString()}
          </span>
        </div>
      </div>
      <div style={styles.alertCardBody}>
        <p style={styles.alertMessage}>{alert.message}</p>
        <div style={styles.alertMeta}>
          <span>📊 {alert.datasource_id}</span>
          <span>🗄️ {alert.datasource_engine}</span>
          <span>Status: {alert.status}</span>
        </div>
      </div>
      <div style={styles.alertCardActions}>
        {alert.status === 'active' && (
          <>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAcknowledge();
              }}
              style={styles.ackButton}
            >
              ✓ Acknowledge
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onResolve();
              }}
              style={styles.resolveButton}
            >
              ✓ Resolve
            </button>
          </>
        )}
        {alert.status === 'acknowledged' && (
          <>
            <span style={styles.statusBadge}>Acknowledged</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onResolve();
              }}
              style={styles.resolveButton}
            >
              ✓ Resolve
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Styles
// ============================================================================

const styles: Record<string, React.CSSProperties> = {
  container: {
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: 'var(--background)',
  },
  header: {
    padding: '15px 20px',
    backgroundColor: 'var(--card)',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tabContainer: {
    display: 'flex',
    gap: '10px',
  },
  tab: {
    padding: '10px 20px',
    backgroundColor: 'var(--muted)',
    color: 'var(--muted-foreground)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    transition: 'all 0.2s',
  },
  activeTab: {
    backgroundColor: 'var(--primary)',
    color: 'var(--primary-foreground)',
    borderColor: 'var(--primary)',
  },
  headerControls: {
    display: 'flex',
    gap: '15px',
    alignItems: 'center',
  },
  autoRefreshLabel: {
    fontSize: '14px',
    cursor: 'pointer',
    color: 'var(--foreground)',
  },
  refreshButton: {
    padding: '8px 16px',
    backgroundColor: 'var(--primary)',
    color: 'var(--primary-foreground)',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
  },
  summary: {
    padding: '15px 20px',
    backgroundColor: 'var(--muted)',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    gap: '30px',
    alignItems: 'center',
  },
  summaryItem: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  summaryLabel: {
    fontSize: '14px',
    color: 'var(--muted-foreground)',
  },
  summaryValue: {
    fontSize: '18px',
    fontWeight: '600',
    color: 'var(--foreground)',
  },
  content: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
  },
  alertList: {
    flex: 1,
    overflowY: 'auto',
    padding: '15px',
  },
  loading: {
    padding: '20px',
    textAlign: 'center',
    fontSize: '16px',
    color: 'var(--muted-foreground)',
  },
  noAlerts: {
    padding: '40px',
    textAlign: 'center',
    fontSize: '18px',
    color: '#10b981',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    border: '1px solid rgba(16, 185, 129, 0.2)',
    borderRadius: '8px',
  },
  severityGroup: {
    marginBottom: '25px',
  },
  severityHeader: {
    margin: '0 0 10px 0',
    fontSize: '16px',
    fontWeight: 'bold',
  },
  p1Color: {
    color: '#dc3545',
  },
  p2Color: {
    color: '#ffc107',
  },
  p3Color: {
    color: '#17a2b8',
  },
  alertCard: {
    backgroundColor: 'var(--card)',
    padding: '15px',
    marginBottom: '10px',
    borderRadius: '8px',
    border: '1px solid var(--border)',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  alertCardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '10px',
  },
  alertTime: {
    fontSize: '12px',
    color: 'var(--muted-foreground)',
  },
  alertCardBody: {
    marginBottom: '10px',
  },
  alertMessage: {
    margin: '0 0 10px 0',
    fontSize: '14px',
    color: 'var(--foreground)',
  },
  alertMeta: {
    display: 'flex',
    gap: '15px',
    fontSize: '12px',
    color: 'var(--muted-foreground)',
  },
  alertCardActions: {
    display: 'flex',
    gap: '10px',
  },
  ackButton: {
    padding: '6px 12px',
    backgroundColor: '#ffc107',
    color: '#000',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: '500',
  },
  resolveButton: {
    padding: '6px 12px',
    backgroundColor: '#28a745',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: '500',
  },
  statusBadge: {
    padding: '6px 12px',
    backgroundColor: 'var(--muted)',
    color: 'var(--muted-foreground)',
    borderRadius: '6px',
    fontSize: '12px',
  },
  resolutionBadge: {
    padding: '4px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    color: '#fff',
    fontWeight: '600',
  },
  detailsPanel: {
    width: '500px',
    backgroundColor: 'var(--card)',
    borderLeft: '1px solid var(--border)',
    overflowY: 'auto',
  },
  detailsTitle: {
    padding: '15px 20px',
    margin: 0,
    borderBottom: '1px solid var(--border)',
    fontSize: '18px',
    fontWeight: 'bold',
    color: 'var(--foreground)',
  },
  detailsContent: {
    padding: '20px',
    color: 'var(--foreground)',
  },
  analysisSection: {
    marginTop: '20px',
    padding: '15px',
    backgroundColor: 'var(--muted)',
    borderRadius: '8px',
    border: '1px solid var(--border)',
  },
  analysisLoading: {
    padding: '20px',
    textAlign: 'center',
    color: 'var(--muted-foreground)',
  },
  rootCause: {
    padding: '12px',
    backgroundColor: 'rgba(251, 191, 36, 0.1)',
    borderLeft: '4px solid #fbbf24',
    marginBottom: '15px',
    borderRadius: '6px',
    border: '1px solid rgba(251, 191, 36, 0.3)',
  },
  confidence: {
    color: 'var(--muted-foreground)',
    fontSize: '12px',
  },
  immediateActions: {
    marginBottom: '15px',
    color: 'var(--foreground)',
  },
  recommendations: {
    marginTop: '15px',
  },
  recommendation: {
    backgroundColor: 'var(--card)',
    padding: '12px',
    marginBottom: '10px',
    borderRadius: '6px',
    border: '1px solid var(--border)',
  },
  recHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: '8px',
  },
  recType: {
    fontSize: '11px',
    fontWeight: 'bold',
    color: 'var(--primary)',
    textTransform: 'uppercase',
  },
  riskBadge: {
    fontSize: '10px',
    padding: '4px 8px',
    borderRadius: '4px',
    color: '#fff',
    fontWeight: '600',
  },
  rationale: {
    fontSize: '13px',
    color: 'var(--muted-foreground)',
    fontStyle: 'italic',
    lineHeight: '1.5',
  },
  codeBlock: {
    padding: '12px',
    backgroundColor: 'var(--muted)',
    borderRadius: '6px',
    fontSize: '12px',
    overflowX: 'auto',
    fontFamily: 'monospace',
    border: '1px solid var(--border)',
    color: 'var(--foreground)',
  },
  improvement: {
    fontSize: '13px',
    color: '#10b981',
    fontWeight: 'bold',
  },
  eta: {
    marginTop: '15px',
    padding: '12px',
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    borderRadius: '6px',
    fontSize: '14px',
    color: '#3b82f6',
    border: '1px solid rgba(59, 130, 246, 0.3)',
  },
};
