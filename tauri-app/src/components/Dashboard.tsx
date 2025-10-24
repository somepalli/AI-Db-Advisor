import { useState, useEffect } from 'react';
import { analyzeApi } from '../api/client';
import type { TopQuery, Lock, Stats } from '../types';

interface Props {
  dataSourceId: string;
}

export function Dashboard({ dataSourceId }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [topQueries, setTopQueries] = useState<TopQuery[]>([]);
  const [locks, setLocks] = useState<Lock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, [dataSourceId]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [statsData, queriesData, locksData] = await Promise.all([
        analyzeApi.getStats(dataSourceId),
        analyzeApi.getTopQueries(dataSourceId, 10).catch(() => []),
        analyzeApi.getLocks(dataSourceId).catch(() => []),
      ]);

      setStats(statsData);
      setTopQueries(queriesData);
      setLocks(locksData);
      setError(null);
    } catch (err) {
      setError('Failed to load dashboard: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div>
      <div className="page-header">
        <h2>Performance Dashboard</h2>
        <p>Overview of {dataSourceId}</p>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <h4>Database Size</h4>
            <div className="value">{formatBytes(stats.total_db_size)}</div>
          </div>
          <div className="stat-card">
            <h4>Active Backends</h4>
            <div className="value">{stats.active_backends}</div>
          </div>
          <div className="stat-card">
            <h4>Active Locks</h4>
            <div className="value">{locks.length}</div>
          </div>
          <div className="stat-card">
            <h4>Top Queries Tracked</h4>
            <div className="value">{topQueries.length}</div>
          </div>
        </div>
      )}

      <div className="card">
        <h3>⚡ Top Queries by Execution Time</h3>
        {topQueries.length === 0 ? (
          <div className="empty-state">
            <p>No query statistics available. Make sure pg_stat_statements extension is installed.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Query</th>
                  <th>Calls</th>
                  <th>Avg Time</th>
                  <th>Rows</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {topQueries.map((query, idx) => (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    <td style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <code>{query.query}</code>
                    </td>
                    <td>{query.calls.toLocaleString()}</td>
                    <td>{query.mean_time_ms.toFixed(2)} ms</td>
                    <td>{query.rows.toLocaleString()}</td>
                    <td>{query.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h3>🔒 Current Database Locks</h3>
        {locks.length === 0 ? (
          <p style={{ color: 'var(--text-secondary)' }}>✅ No active locks detected.</p>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Lock Type</th>
                  <th>Mode</th>
                  <th>Granted</th>
                  <th>PID</th>
                  <th>Age</th>
                </tr>
              </thead>
              <tbody>
                {locks.map((lock, idx) => (
                  <tr key={idx}>
                    <td>{lock.locktype}</td>
                    <td>{lock.mode}</td>
                    <td>{lock.granted ? '✅' : '❌'}</td>
                    <td>{lock.pid}</td>
                    <td>{lock.age}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
