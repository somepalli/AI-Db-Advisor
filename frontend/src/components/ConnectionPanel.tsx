import { useState, useEffect } from 'react';
import { datasourcesApi, analyzeApi } from '../api/client';
import { connectionStore } from '../utils/store';
import type { DataSource, DataSourceCreate, Lock, Stats, TopQuery } from '../types';

interface Props {
  onSelectDataSource: (dsId: string) => void;
  selectedDataSource: string | null;
}

type Tab = 'connections' | 'locks' | 'stats' | 'queries';

export function ConnectionPanel({ onSelectDataSource, selectedDataSource }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('connections');
  const [dataSources, setDataSources] = useState<Record<string, DataSource>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<DataSourceCreate>({
    id: '',
    engine: 'postgres',
    dsn: '',
  });

  const getDSNPlaceholder = () => {
    switch (formData.engine) {
      case 'postgres':
        return 'postgresql://user:pass@host:5432/db';
      case 'mysql':
      case 'mariadb':
        return 'mysql://user:pass@host:3306/db';
      case 'sqlserver':
      case 'mssql':
        return 'mssql://user:pass@host:1433/db';
      case 'mongodb':
      case 'mongo':
        return 'mongodb://user:pass@host:27017/db';
      case 'oracle':
        return 'oracle://user:pass@host:1521/service';
      case 'redis':
        return 'redis://host:6379/0';
      case 'sqlite':
        return 'sqlite:///path/to/database.db';
      default:
        return 'database://user:pass@host:port/db';
    }
  };

  // Dashboard data
  const [locks, setLocks] = useState<Lock[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [topQueries, setTopQueries] = useState<TopQuery[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(false);

  useEffect(() => {
    loadDataSources();
  }, []);

  useEffect(() => {
    if (selectedDataSource && activeTab !== 'connections') {
      loadDashboardData();
    }
  }, [selectedDataSource, activeTab]);

  const loadDataSources = async () => {
    try {
      setLoading(true);
      const savedConnections = connectionStore.getAll();

      for (const conn of savedConnections) {
        try {
          await datasourcesApi.create({
            id: conn.id,
            engine: conn.engine,
            dsn: conn.dsn,
          });
        } catch (err) {
          console.log(`Connection ${conn.id} already registered or failed to register`);
        }
      }

      const data = await datasourcesApi.list();
      setDataSources(data);
      setError(null);
    } catch (err) {
      setError('Failed to load data sources: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadDashboardData = async () => {
    if (!selectedDataSource) return;

    try {
      setDashboardLoading(true);
      const [statsData, queriesData, locksData] = await Promise.all([
        analyzeApi.getStats(selectedDataSource),
        analyzeApi.getTopQueries(selectedDataSource, 5).catch(() => []),
        analyzeApi.getLocks(selectedDataSource).catch(() => []),
      ]);

      setStats(statsData);
      setTopQueries(queriesData);
      setLocks(locksData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setDashboardLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await datasourcesApi.create(formData);
      connectionStore.save({
        id: formData.id,
        engine: formData.engine,
        dsn: formData.dsn,
      });

      setShowForm(false);
      setFormData({ id: '', engine: 'postgres', dsn: '' });
      loadDataSources();
    } catch (err) {
      setError('Failed to create data source: ' + (err as Error).message);
    }
  };

  const handleDelete = async (dsId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent selecting the datasource when clicking delete

    if (!confirm(`Are you sure you want to delete connection "${dsId}"?`)) {
      return;
    }

    try {
      await datasourcesApi.delete(dsId);
      connectionStore.delete(dsId);

      // If we deleted the selected datasource, clear selection
      if (selectedDataSource === dsId) {
        onSelectDataSource('');
      }

      loadDataSources();
      setError(null);
    } catch (err) {
      setError('Failed to delete data source: ' + (err as Error).message);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  if (loading) {
    return <div style={{ padding: '16px', color: 'var(--text-secondary)' }}>Loading...</div>;
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Tabs */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-color)',
        backgroundColor: 'var(--bg-secondary)',
      }}>
        <button
          onClick={() => setActiveTab('connections')}
          style={{
            flex: 1,
            padding: '10px 8px',
            border: 'none',
            backgroundColor: activeTab === 'connections' ? 'var(--bg-primary)' : 'transparent',
            borderBottom: activeTab === 'connections' ? '2px solid var(--primary)' : 'none',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: activeTab === 'connections' ? 600 : 400,
            color: activeTab === 'connections' ? 'var(--primary)' : 'var(--text-secondary)',
          }}
        >
          Connections
        </button>
        <button
          onClick={() => setActiveTab('stats')}
          disabled={!selectedDataSource}
          style={{
            flex: 1,
            padding: '10px 8px',
            border: 'none',
            backgroundColor: activeTab === 'stats' ? 'var(--bg-primary)' : 'transparent',
            borderBottom: activeTab === 'stats' ? '2px solid var(--primary)' : 'none',
            cursor: selectedDataSource ? 'pointer' : 'not-allowed',
            fontSize: '12px',
            fontWeight: activeTab === 'stats' ? 600 : 400,
            color: activeTab === 'stats' ? 'var(--primary)' : 'var(--text-secondary)',
            opacity: selectedDataSource ? 1 : 0.5,
          }}
        >
          Stats
        </button>
        <button
          onClick={() => setActiveTab('locks')}
          disabled={!selectedDataSource}
          style={{
            flex: 1,
            padding: '10px 8px',
            border: 'none',
            backgroundColor: activeTab === 'locks' ? 'var(--bg-primary)' : 'transparent',
            borderBottom: activeTab === 'locks' ? '2px solid var(--primary)' : 'none',
            cursor: selectedDataSource ? 'pointer' : 'not-allowed',
            fontSize: '12px',
            fontWeight: activeTab === 'locks' ? 600 : 400,
            color: activeTab === 'locks' ? 'var(--primary)' : 'var(--text-secondary)',
            opacity: selectedDataSource ? 1 : 0.5,
          }}
        >
          Locks
        </button>
        <button
          onClick={() => setActiveTab('queries')}
          disabled={!selectedDataSource}
          style={{
            flex: 1,
            padding: '10px 8px',
            border: 'none',
            backgroundColor: activeTab === 'queries' ? 'var(--bg-primary)' : 'transparent',
            borderBottom: activeTab === 'queries' ? '2px solid var(--primary)' : 'none',
            cursor: selectedDataSource ? 'pointer' : 'not-allowed',
            fontSize: '12px',
            fontWeight: activeTab === 'queries' ? 600 : 400,
            color: activeTab === 'queries' ? 'var(--primary)' : 'var(--text-secondary)',
            opacity: selectedDataSource ? 1 : 0.5,
          }}
        >
          Queries
        </button>
      </div>

      {/* Tab Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {error && (
          <div style={{
            padding: '12px',
            backgroundColor: 'var(--error-bg)',
            color: 'var(--error)',
            borderRadius: '6px',
            marginBottom: '12px',
            fontSize: '12px',
          }}>
            {error}
          </div>
        )}

        {/* Connections Tab */}
        {activeTab === 'connections' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
              <h4 style={{ fontSize: '14px', margin: 0 }}>Data Sources</h4>
              <button
                onClick={() => setShowForm(!showForm)}
                style={{
                  padding: '4px 12px',
                  fontSize: '12px',
                  backgroundColor: 'var(--primary)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                {showForm ? 'Cancel' : '+ Add'}
              </button>
            </div>

            {showForm && (
              <form onSubmit={handleSubmit} style={{
                marginBottom: '16px',
                padding: '12px',
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: '6px',
              }}>
                <div style={{ marginBottom: '8px' }}>
                  <label style={{ fontSize: '11px', fontWeight: 500, display: 'block', marginBottom: '4px' }}>
                    ID
                  </label>
                  <input
                    type="text"
                    value={formData.id}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    placeholder="my-db"
                    required
                    style={{
                      width: '100%',
                      padding: '6px',
                      fontSize: '12px',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div style={{ marginBottom: '8px' }}>
                  <label style={{ fontSize: '11px', fontWeight: 500, display: 'block', marginBottom: '4px' }}>
                    Engine
                  </label>
                  <select
                    value={formData.engine}
                    onChange={(e) => setFormData({ ...formData, engine: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '6px',
                      fontSize: '12px',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                    }}
                  >
                    <optgroup label="SQL Databases">
                      <option value="postgres">PostgreSQL</option>
                      <option value="mysql">MySQL / MariaDB</option>
                      <option value="sqlserver">Microsoft SQL Server</option>
                      <option value="oracle">Oracle Database</option>
                    </optgroup>
                    <optgroup label="NoSQL Databases">
                      <option value="mongodb">MongoDB</option>
                      <option value="redis">Redis</option>
                      <option value="cassandra">Cassandra</option>
                    </optgroup>
                    <optgroup label="Other">
                      <option value="sqlite">SQLite</option>
                    </optgroup>
                  </select>
                </div>
                <div style={{ marginBottom: '8px' }}>
                  <label style={{ fontSize: '11px', fontWeight: 500, display: 'block', marginBottom: '4px' }}>
                    DSN
                  </label>
                  <input
                    type="text"
                    value={formData.dsn}
                    onChange={(e) => setFormData({ ...formData, dsn: e.target.value })}
                    placeholder={getDSNPlaceholder()}
                    required
                    style={{
                      width: '100%',
                      padding: '6px',
                      fontSize: '12px',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <button
                  type="submit"
                  style={{
                    width: '100%',
                    padding: '6px',
                    fontSize: '12px',
                    backgroundColor: 'var(--primary)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  Create
                </button>
              </form>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {Object.keys(dataSources).length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                  No connections
                </div>
              ) : (
                Object.entries(dataSources).map(([id, ds]) => (
                  <div
                    key={id}
                    onClick={() => onSelectDataSource(id)}
                    style={{
                      padding: '10px',
                      border: selectedDataSource === id ? '2px solid var(--primary)' : '1px solid var(--border-color)',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      backgroundColor: selectedDataSource === id ? 'rgba(37, 99, 235, 0.05)' : 'white',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>{id}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {ds.engine}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDelete(id, e)}
                      style={{
                        padding: '4px 8px',
                        fontSize: '16px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--error)',
                        opacity: 0.6,
                        transition: 'opacity 0.2s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                      onMouseLeave={(e) => e.currentTarget.style.opacity = '0.6'}
                      title={`Delete ${id}`}
                    >
                      🗑️
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Stats Tab */}
        {activeTab === 'stats' && (
          <div>
            {dashboardLoading ? (
              <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Loading stats...</div>
            ) : stats ? (
              <div>
                <div style={{ marginBottom: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Database Size
                  </div>
                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--primary)' }}>
                    {formatBytes(stats.total_db_size)}
                  </div>
                </div>
                <div style={{ marginBottom: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Active Backends
                  </div>
                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--primary)' }}>
                    {stats.active_backends}
                  </div>
                </div>
                <button
                  onClick={loadDashboardData}
                  style={{
                    marginTop: '12px',
                    padding: '6px 12px',
                    fontSize: '12px',
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  🔄 Refresh
                </button>
              </div>
            ) : (
              <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                No stats available
              </div>
            )}
          </div>
        )}

        {/* Locks Tab */}
        {activeTab === 'locks' && (
          <div>
            {dashboardLoading ? (
              <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Loading locks...</div>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <h4 style={{ fontSize: '14px', margin: 0 }}>
                    Active Locks ({locks.length})
                  </h4>
                  <button
                    onClick={loadDashboardData}
                    style={{
                      padding: '4px 8px',
                      fontSize: '11px',
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                      cursor: 'pointer',
                    }}
                  >
                    🔄
                  </button>
                </div>

                {locks.length === 0 ? (
                  <div style={{ color: 'var(--success-color)', fontSize: '12px', padding: '12px', textAlign: 'center' }}>
                    ✅ No active locks
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {locks.map((lock, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '10px',
                          backgroundColor: 'var(--bg-secondary)',
                          borderRadius: '6px',
                          fontSize: '11px',
                        }}
                      >
                        <div style={{ fontWeight: 600, marginBottom: '4px' }}>{lock.locktype}</div>
                        <div style={{ color: 'var(--text-secondary)' }}>Mode: {lock.mode}</div>
                        <div style={{ color: 'var(--text-secondary)' }}>
                          PID: {lock.pid} | {lock.granted ? '✅ Granted' : '❌ Waiting'}
                        </div>
                        <div style={{ color: 'var(--text-secondary)' }}>Age: {lock.age}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Top Queries Tab */}
        {activeTab === 'queries' && (
          <div>
            {dashboardLoading ? (
              <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Loading queries...</div>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <h4 style={{ fontSize: '14px', margin: 0 }}>
                    Top Queries ({topQueries.length})
                  </h4>
                  <button
                    onClick={loadDashboardData}
                    style={{
                      padding: '4px 8px',
                      fontSize: '11px',
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                      cursor: 'pointer',
                    }}
                  >
                    🔄
                  </button>
                </div>

                {topQueries.length === 0 ? (
                  <div style={{ color: 'var(--text-secondary)', fontSize: '12px', padding: '12px', textAlign: 'center' }}>
                    No query statistics available
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {topQueries.map((query, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '10px',
                          backgroundColor: 'var(--bg-secondary)',
                          borderRadius: '6px',
                          fontSize: '11px',
                        }}
                      >
                        <div style={{ fontWeight: 600, marginBottom: '4px', color: 'var(--primary)' }}>
                          #{idx + 1}
                        </div>
                        <div
                          style={{
                            fontFamily: 'monospace',
                            fontSize: '10px',
                            marginBottom: '6px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            backgroundColor: 'white',
                            padding: '4px',
                            borderRadius: '3px',
                          }}
                          title={query.query}
                        >
                          {query.query}
                        </div>
                        <div style={{ display: 'flex', gap: '12px', fontSize: '10px', color: 'var(--text-secondary)' }}>
                          <span>Calls: {query.calls}</span>
                          <span>Avg: {query.mean_time_ms.toFixed(2)}ms</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
