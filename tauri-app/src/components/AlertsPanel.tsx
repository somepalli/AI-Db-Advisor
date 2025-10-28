/**
 * AlertsPanel Component - Three-tab alert management system
 *
 * Displays alerts in three tabs:
 * 1. Current - Active and acknowledged alerts
 * 2. Resolved - Resolved alerts with automatic/manual tags
 * 3. All - Complete alert history with status breakdown
 */

import React, { useState, useEffect } from 'react';

// Types
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
  metadata?: any;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  auto_resolved: boolean;
  resolution_type?: 'automatic' | 'manual' | null;
}

interface AlertsResponse {
  alerts: Alert[];
  count: number;
  summary?: {
    active: number;
    acknowledged: number;
    resolved: number;
    auto_resolved: number;
  };
}

type TabType = 'current' | 'resolved' | 'all';

const API_BASE = 'http://127.0.0.1:8095';

// Severity badge colors
const severityColors = {
  P1: '#dc2626', // red-600
  P2: '#ea580c', // orange-600
  P3: '#ca8a04', // yellow-600
};

// Status badge colors
const statusColors = {
  active: '#dc2626',       // red-600
  acknowledged: '#f97316', // orange-500
  resolved: '#16a34a',     // green-600
  auto_resolved: '#059669', // green-500
};

export default function AlertsPanel() {
  const [activeTab, setActiveTab] = useState<TabType>('current');
  const [currentAlerts, setCurrentAlerts] = useState<Alert[]>([]);
  const [resolvedAlerts, setResolvedAlerts] = useState<Alert[]>([]);
  const [allAlerts, setAllAlerts] = useState<Alert[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Fetch alerts based on active tab
  const fetchAlerts = async () => {
    setLoading(true);
    setError(null);

    try {
      if (activeTab === 'current') {
        const response = await fetch(`${API_BASE}/alerts/active`);
        const data: AlertsResponse = await response.json();
        setCurrentAlerts(data.alerts);
      } else if (activeTab === 'resolved') {
        const response = await fetch(`${API_BASE}/alerts/resolved?limit=50`);
        const data: AlertsResponse = await response.json();
        setResolvedAlerts(data.alerts);
      } else if (activeTab === 'all') {
        const response = await fetch(`${API_BASE}/alerts/all?limit=100`);
        const data: AlertsResponse = await response.json();
        setAllAlerts(data.alerts);
        if (data.summary) {
          setSummary(data.summary);
        }
      }
    } catch (err) {
      setError(`Failed to fetch alerts: ${err}`);
      console.error('Error fetching alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh effect
  useEffect(() => {
    fetchAlerts();

    if (autoRefresh) {
      const interval = setInterval(fetchAlerts, 10000); // Refresh every 10 seconds
      return () => clearInterval(interval);
    }
  }, [activeTab, autoRefresh]);

  // Acknowledge alert
  const handleAcknowledge = async (alertId: string) => {
    try {
      const encoded = encodeURIComponent(alertId);
      const response = await fetch(`${API_BASE}/alerts/${encoded}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          acknowledged_by: 'User',
          notes: 'Acknowledged via UI'
        })
      });

      if (response.ok) {
        fetchAlerts(); // Refresh
      } else {
        alert('Failed to acknowledge alert');
      }
    } catch (err) {
      console.error('Error acknowledging alert:', err);
      alert('Failed to acknowledge alert');
    }
  };

  // Resolve alert manually
  const handleResolve = async (alertId: string) => {
    try {
      const encoded = encodeURIComponent(alertId);
      const response = await fetch(`${API_BASE}/alerts/${encoded}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resolved_by: 'User',
          notes: 'Manually resolved via UI'
        })
      });

      if (response.ok) {
        fetchAlerts(); // Refresh
      } else {
        alert('Failed to resolve alert');
      }
    } catch (err) {
      console.error('Error resolving alert:', err);
      alert('Failed to resolve alert');
    }
  };

  // Format timestamp
  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  // Calculate time ago
  const timeAgo = (isoString: string) => {
    const now = new Date().getTime();
    const then = new Date(isoString).getTime();
    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  // Render single alert card
  const renderAlert = (alert: Alert, showActions: boolean = true) => (
    <div
      key={alert.id}
      style={{
        border: `2px solid ${severityColors[alert.severity]}`,
        borderRadius: '8px',
        padding: '16px',
        marginBottom: '12px',
        backgroundColor: '#ffffff',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
            <span
              style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: 'bold',
                color: '#fff',
                backgroundColor: severityColors[alert.severity]
              }}
            >
              {alert.severity}
            </span>
            <span
              style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: '500',
                color: '#fff',
                backgroundColor: statusColors[alert.status]
              }}
            >
              {alert.status}
            </span>
            {alert.resolution_type && (
              <span
                style={{
                  display: 'inline-block',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: '500',
                  color: '#fff',
                  backgroundColor: alert.resolution_type === 'automatic' ? '#059669' : '#0891b2'
                }}
              >
                {alert.resolution_type === 'automatic' ? '🤖 Auto-Resolved' : '👤 Manual-Resolved'}
              </span>
            )}
          </div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: '600', color: '#111' }}>
            {alert.title}
          </h3>
          <p style={{ margin: '0', fontSize: '13px', color: '#666' }}>
            {alert.datasource_id} ({alert.datasource_engine})
          </p>
        </div>
        <div style={{ fontSize: '12px', color: '#999', textAlign: 'right' }}>
          {timeAgo(alert.triggered_at)}
        </div>
      </div>

      {/* Message */}
      <div style={{ marginBottom: '12px' }}>
        <p style={{ margin: '0', fontSize: '14px', color: '#444', lineHeight: '1.5' }}>
          {alert.message}
        </p>
      </div>

      {/* Metrics */}
      {(alert.metric_value !== undefined || alert.threshold !== undefined) && (
        <div style={{ marginBottom: '12px', padding: '8px', backgroundColor: '#f9fafb', borderRadius: '4px' }}>
          <span style={{ fontSize: '12px', color: '#666' }}>
            <strong>Metric:</strong> {alert.metric_value} | <strong>Threshold:</strong> {alert.threshold}
          </span>
        </div>
      )}

      {/* AI Analysis Section */}
      {alert.metadata?.ai_analysis && !alert.metadata.ai_analysis.error && (
        <div style={{
          marginBottom: '12px',
          padding: '12px',
          backgroundColor: '#f0f9ff',
          borderLeft: '4px solid #3b82f6',
          borderRadius: '4px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <span style={{ fontSize: '16px' }}>🤖</span>
            <strong style={{ fontSize: '13px', color: '#1e40af' }}>AI Analysis</strong>
          </div>

          {/* Root Cause */}
          {alert.metadata.ai_analysis.root_cause && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '12px', fontWeight: '600', color: '#374151', marginBottom: '4px' }}>
                Root Cause:
              </div>
              <div style={{ fontSize: '13px', color: '#4b5563', lineHeight: '1.5' }}>
                {alert.metadata.ai_analysis.root_cause}
              </div>
            </div>
          )}

          {/* Risk Level */}
          {alert.metadata.ai_analysis.risk_level && (
            <div style={{ marginBottom: '10px' }}>
              <span style={{ fontSize: '12px', fontWeight: '600', color: '#374151' }}>Risk Level: </span>
              <span style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 'bold',
                color: '#fff',
                backgroundColor: alert.metadata.ai_analysis.risk_level === 'high' ? '#dc2626' :
                                alert.metadata.ai_analysis.risk_level === 'medium' ? '#f59e0b' : '#16a34a'
              }}>
                {alert.metadata.ai_analysis.risk_level.toUpperCase()}
              </span>
            </div>
          )}

          {/* Immediate Actions */}
          {alert.metadata.ai_analysis.immediate_actions && alert.metadata.ai_analysis.immediate_actions.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '12px', fontWeight: '600', color: '#374151', marginBottom: '6px' }}>
                ⚡ Immediate Actions:
              </div>
              <ul style={{ margin: '0', paddingLeft: '20px', fontSize: '13px', color: '#4b5563', lineHeight: '1.6' }}>
                {alert.metadata.ai_analysis.immediate_actions.map((action: string, idx: number) => (
                  <li key={idx}>{action}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Runbook Steps (Collapsible) */}
          {alert.metadata.ai_analysis.runbook_steps && alert.metadata.ai_analysis.runbook_steps.length > 0 && (
            <details style={{ marginTop: '8px' }}>
              <summary style={{
                fontSize: '12px',
                fontWeight: '600',
                color: '#374151',
                cursor: 'pointer',
                userSelect: 'none'
              }}>
                📋 Detailed Runbook Steps ({alert.metadata.ai_analysis.runbook_steps.length})
              </summary>
              <ol style={{ margin: '8px 0 0 0', paddingLeft: '20px', fontSize: '13px', color: '#4b5563', lineHeight: '1.6' }}>
                {alert.metadata.ai_analysis.runbook_steps.map((step: string, idx: number) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>{step}</li>
                ))}
              </ol>
            </details>
          )}

          {/* Estimated Impact */}
          {alert.metadata.ai_analysis.estimated_impact && (
            <div style={{ marginTop: '10px', fontSize: '12px', color: '#6b7280', fontStyle: 'italic' }}>
              💡 Impact: {alert.metadata.ai_analysis.estimated_impact}
            </div>
          )}
        </div>
      )}

      {/* Timestamps */}
      <div style={{ marginBottom: '12px', fontSize: '12px', color: '#666' }}>
        <div><strong>Triggered:</strong> {formatTime(alert.triggered_at)}</div>
        {alert.acknowledged_at && (
          <div><strong>Acknowledged:</strong> {formatTime(alert.acknowledged_at)} by {alert.acknowledged_by}</div>
        )}
        {alert.resolved_at && (
          <div><strong>Resolved:</strong> {formatTime(alert.resolved_at)}</div>
        )}
      </div>

      {/* Actions */}
      {showActions && (alert.status === 'active' || alert.status === 'acknowledged') && (
        <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
          {alert.status === 'active' && (
            <button
              onClick={() => handleAcknowledge(alert.id)}
              style={{
                padding: '6px 12px',
                fontSize: '13px',
                fontWeight: '500',
                color: '#fff',
                backgroundColor: '#f97316',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Acknowledge
            </button>
          )}
          <button
            onClick={() => handleResolve(alert.id)}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              fontWeight: '500',
              color: '#fff',
              backgroundColor: '#16a34a',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Resolve Manually
          </button>
        </div>
      )}
    </div>
  );

  // Get alerts for current tab
  const getAlertsForTab = () => {
    if (activeTab === 'current') return currentAlerts;
    if (activeTab === 'resolved') return resolvedAlerts;
    return allAlerts;
  };

  const alerts = getAlertsForTab();

  return (
    <div style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', color: '#111' }}>
            Alerts Dashboard
          </h2>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <label style={{ fontSize: '13px', color: '#666', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              Auto-refresh (10s)
            </label>
            <button
              onClick={fetchAlerts}
              style={{
                padding: '6px 12px',
                fontSize: '13px',
                fontWeight: '500',
                color: '#fff',
                backgroundColor: '#2563eb',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Refresh Now
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '4px', borderBottom: '2px solid #e5e7eb' }}>
          <button
            onClick={() => setActiveTab('current')}
            style={{
              padding: '12px 24px',
              fontSize: '14px',
              fontWeight: '600',
              color: activeTab === 'current' ? '#2563eb' : '#666',
              backgroundColor: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'current' ? '3px solid #2563eb' : '3px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            Current {currentAlerts.length > 0 && `(${currentAlerts.length})`}
          </button>
          <button
            onClick={() => setActiveTab('resolved')}
            style={{
              padding: '12px 24px',
              fontSize: '14px',
              fontWeight: '600',
              color: activeTab === 'resolved' ? '#2563eb' : '#666',
              backgroundColor: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'resolved' ? '3px solid #2563eb' : '3px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            Resolved {resolvedAlerts.length > 0 && `(${resolvedAlerts.length})`}
          </button>
          <button
            onClick={() => setActiveTab('all')}
            style={{
              padding: '12px 24px',
              fontSize: '14px',
              fontWeight: '600',
              color: activeTab === 'all' ? '#2563eb' : '#666',
              backgroundColor: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'all' ? '3px solid #2563eb' : '3px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            All {allAlerts.length > 0 && `(${allAlerts.length})`}
          </button>
        </div>

        {/* Summary for "All" tab */}
        {activeTab === 'all' && summary && (
          <div style={{ marginTop: '12px', display: 'flex', gap: '12px' }}>
            <div style={{ padding: '8px 12px', backgroundColor: '#fef2f2', borderRadius: '6px' }}>
              <span style={{ fontSize: '12px', color: '#666' }}>Active: </span>
              <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#dc2626' }}>{summary.active}</span>
            </div>
            <div style={{ padding: '8px 12px', backgroundColor: '#fff7ed', borderRadius: '6px' }}>
              <span style={{ fontSize: '12px', color: '#666' }}>Acknowledged: </span>
              <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#f97316' }}>{summary.acknowledged}</span>
            </div>
            <div style={{ padding: '8px 12px', backgroundColor: '#f0fdf4', borderRadius: '6px' }}>
              <span style={{ fontSize: '12px', color: '#666' }}>Resolved: </span>
              <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#16a34a' }}>{summary.resolved}</span>
            </div>
            <div style={{ padding: '8px 12px', backgroundColor: '#ecfdf5', borderRadius: '6px' }}>
              <span style={{ fontSize: '12px', color: '#666' }}>Auto-Resolved: </span>
              <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#059669' }}>{summary.auto_resolved}</span>
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
            Loading alerts...
          </div>
        )}

        {error && (
          <div style={{ padding: '16px', backgroundColor: '#fee2e2', color: '#991b1b', borderRadius: '6px' }}>
            {error}
          </div>
        )}

        {!loading && !error && alerts.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
            <p style={{ fontSize: '16px', marginBottom: '8px' }}>No alerts found</p>
            <p style={{ fontSize: '13px', color: '#bbb' }}>
              {activeTab === 'current' && 'All systems are running normally'}
              {activeTab === 'resolved' && 'No resolved alerts in history'}
              {activeTab === 'all' && 'No alerts have been triggered yet'}
            </p>
          </div>
        )}

        {!loading && !error && alerts.length > 0 && (
          <div>
            {alerts.map(alert => renderAlert(alert, activeTab === 'current'))}
          </div>
        )}
      </div>
    </div>
  );
}
