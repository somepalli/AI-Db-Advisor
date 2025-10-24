import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  analyticsApi,
  datasourcesApi,
  type SyncStatus,
  type AnalyticsResult,
  type DataSource,
} from '../api/client';

interface Props {
  pgDataSourceId: string;
  chDataSourceId: string;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];

export function AnalyticsDashboard({ pgDataSourceId, chDataSourceId }: Props) {
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datasources, setDatasources] = useState<Record<string, DataSource>>({});

  // Dashboard data
  const [kpisData, setKpisData] = useState<AnalyticsResult | null>(null);
  const [enrollmentTrends, setEnrollmentTrends] = useState<AnalyticsResult | null>(null);
  const [departmentDist, setDepartmentDist] = useState<AnalyticsResult | null>(null);
  const [gradesDist, setGradesDist] = useState<AnalyticsResult | null>(null);
  const [libraryAnalytics, setLibraryAnalytics] = useState<AnalyticsResult | null>(null);
  const [hostelAnalytics, setHostelAnalytics] = useState<AnalyticsResult | null>(null);

  const [loadingDashboard, setLoadingDashboard] = useState(false);

  useEffect(() => {
    loadDatasources();
    loadSyncStatus();
    loadDashboardData();
  }, [pgDataSourceId, chDataSourceId]);

  const loadDatasources = async () => {
    try {
      const data = await datasourcesApi.list();
      setDatasources(data);
    } catch (err) {
      console.error('Failed to load datasources:', err);
    }
  };

  const loadSyncStatus = async () => {
    if (!pgDataSourceId || !chDataSourceId) return;

    setLoading(true);
    setError(null);

    try {
      const status = await analyticsApi.getSyncStatus({
        pg_ds_id: pgDataSourceId,
        ch_ds_id: chDataSourceId,
      });
      setSyncStatus(status);
    } catch (err: any) {
      setError(err.message || 'Failed to load sync status');
    } finally {
      setLoading(false);
    }
  };

  const handleSyncAll = async () => {
    if (!pgDataSourceId || !chDataSourceId) return;

    setSyncing(true);
    setError(null);

    try {
      const result = await analyticsApi.syncAllTables({
        pg_ds_id: pgDataSourceId,
        ch_ds_id: chDataSourceId,
        batch_size: 1000,
      });

      if (result.success) {
        alert(`✅ Synced ${result.tables_synced} tables (${result.total_rows} rows)`);
        await loadSyncStatus();
        await loadDashboardData();
      } else {
        setError(result.error || 'Sync failed');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to sync data');
    } finally {
      setSyncing(false);
    }
  };

  const loadDashboardData = async () => {
    if (!chDataSourceId) return;

    setLoadingDashboard(true);
    setError(null);

    try {
      // Load all dashboard endpoints in parallel
      const [kpis, trends, deptDist, grades, library, hostel] = await Promise.all([
        analyticsApi.getDashboardKPIs(chDataSourceId),
        analyticsApi.getEnrollmentTrends(chDataSourceId),
        analyticsApi.getDepartmentDistribution(chDataSourceId),
        analyticsApi.getGradeDistribution(chDataSourceId),
        analyticsApi.getLibraryAnalytics(chDataSourceId),
        analyticsApi.getHostelAnalytics(chDataSourceId),
      ]);

      setKpisData(kpis);
      setEnrollmentTrends(trends);
      setDepartmentDist(deptDist);
      setGradesDist(grades);
      setLibraryAnalytics(library);
      setHostelAnalytics(hostel);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoadingDashboard(false);
    }
  };

  const renderKPICard = (title: string, value: string | number, subtitle?: string, color: string = '#3b82f6') => (
    <div style={{
      padding: '20px',
      backgroundColor: 'hsl(var(--card))',
      border: '1px solid hsl(var(--border))',
      borderRadius: '8px',
      borderLeft: `4px solid ${color}`,
    }}>
      <div style={{ fontSize: '12px', color: 'hsl(var(--muted-foreground))', marginBottom: '8px', textTransform: 'uppercase' }}>
        {title}
      </div>
      <div style={{ fontSize: '28px', fontWeight: 700, color: 'hsl(var(--foreground))', marginBottom: '4px' }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {subtitle && (
        <div style={{ fontSize: '12px', color: 'hsl(var(--muted-foreground))' }}>
          {subtitle}
        </div>
      )}
    </div>
  );

  return (
    <div style={{ padding: '20px', backgroundColor: 'hsl(var(--background))', height: '100%', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 700, color: 'hsl(var(--foreground))' }}>
          📊 Analytics Dashboard
        </h1>
        <button
          onClick={loadDashboardData}
          disabled={loadingDashboard}
          style={{
            padding: '10px 20px',
            fontSize: '14px',
            backgroundColor: 'hsl(var(--primary))',
            color: 'hsl(var(--primary-foreground))',
            border: 'none',
            borderRadius: '6px',
            cursor: loadingDashboard ? 'not-allowed' : 'pointer',
            opacity: loadingDashboard ? 0.6 : 1,
            transition: 'all 0.2s',
          }}
        >
          {loadingDashboard ? '⏳ Loading...' : '🔄 Refresh Dashboard'}
        </button>
      </div>

      {/* Connection Status */}
      <div style={{ marginBottom: '24px', padding: '16px', backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}>
        <h2 style={{ marginBottom: '12px', fontSize: '16px', fontWeight: 600, color: 'hsl(var(--foreground))' }}>Connections</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <div style={{ fontSize: '12px', color: 'hsl(var(--muted-foreground))', marginBottom: '4px' }}>
              PostgreSQL (Source)
            </div>
            <div style={{ fontWeight: 500, color: 'hsl(var(--foreground))' }}>
              {datasources[pgDataSourceId]?.id || pgDataSourceId}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '12px', color: 'hsl(var(--muted-foreground))', marginBottom: '4px' }}>
              DuckDB (Analytics)
            </div>
            <div style={{ fontWeight: 500, color: 'hsl(var(--foreground))' }}>
              {datasources[chDataSourceId]?.id || chDataSourceId}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '12px',
            backgroundColor: 'hsl(var(--destructive) / 0.1)',
            color: 'hsl(var(--destructive))',
            border: '1px solid hsl(var(--destructive) / 0.3)',
            borderRadius: '6px',
            marginBottom: '24px',
          }}
        >
          {error}
        </div>
      )}

      {/* KPIs Section */}
      {kpisData && kpisData.success && kpisData.rows.length > 0 && (
        <div style={{ marginBottom: '32px' }}>
          <h2 style={{ marginBottom: '16px', fontSize: '20px', fontWeight: 600, color: 'hsl(var(--foreground))' }}>
            🎯 Key Performance Indicators
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
            {renderKPICard('Total Students', kpisData.rows[0].total_students, `${kpisData.rows[0].total_departments} Departments`, '#3b82f6')}
            {renderKPICard('Total Revenue', `₹${(kpisData.rows[0].total_revenue / 1000000).toFixed(2)}M`, `${kpisData.rows[0].collection_rate}% collected`, '#10b981')}
            {renderKPICard('Library Loans', kpisData.rows[0].total_loans, `${kpisData.rows[0].active_borrowers} active borrowers`, '#f59e0b')}
            {renderKPICard('Hostel Occupancy', `${kpisData.rows[0].hostel_occupancy_rate?.toFixed(1)}%`, `${kpisData.rows[0].hostel_occupied} students`, '#8b5cf6')}
          </div>
        </div>
      )}

      {/* Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '24px' }}>

        {/* Enrollment Trends */}
        {enrollmentTrends && enrollmentTrends.success && enrollmentTrends.rows.length > 0 && (
          <div style={{ padding: '20px', backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}>
            <h3 style={{ marginBottom: '16px', fontSize: '16px', fontWeight: 600, color: 'hsl(var(--foreground))' }}>
              📈 Enrollment Trends
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={enrollmentTrends.rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="enrollment_year" stroke="hsl(var(--muted-foreground))" />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '6px',
                  }}
                />
                <Legend />
                <Line type="monotone" dataKey="student_count" stroke="#3b82f6" strokeWidth={2} name="Students" />
                <Line type="monotone" dataKey="growth_rate" stroke="#10b981" strokeWidth={2} name="Growth %" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Department Distribution */}
        {departmentDist && departmentDist.success && departmentDist.rows.length > 0 && (
          <div style={{ padding: '20px', backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}>
            <h3 style={{ marginBottom: '16px', fontSize: '16px', fontWeight: 600, color: 'hsl(var(--foreground))' }}>
              🏫 Department Distribution
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={departmentDist.rows.slice(0, 8)}
                  dataKey="student_count"
                  nameKey="department_name"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={(entry) => entry.department_name}
                >
                  {departmentDist.rows.slice(0, 8).map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '6px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Grade Distribution */}
        {gradesDist && gradesDist.success && gradesDist.rows.length > 0 && (
          <div style={{ padding: '20px', backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}>
            <h3 style={{ marginBottom: '16px', fontSize: '16px', fontWeight: 600, color: 'hsl(var(--foreground))' }}>
              📊 Grade Distribution (Top Department)
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={gradesDist.rows.filter((r) => r.department_name === gradesDist.rows[0].department_name)}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="grade" stroke="hsl(var(--muted-foreground))" />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '6px',
                  }}
                />
                <Legend />
                <Bar dataKey="count" fill="#3b82f6" name="Students" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Library Analytics */}
        {libraryAnalytics && libraryAnalytics.success && libraryAnalytics.rows.length > 0 && (
          <div style={{ padding: '20px', backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}>
            <h3 style={{ marginBottom: '16px', fontSize: '16px', fontWeight: 600, color: 'hsl(var(--foreground))' }}>
              📚 Top 10 Most Borrowed Books
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={libraryAnalytics.rows.slice(0, 10)} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis type="number" stroke="hsl(var(--muted-foreground))" />
                <YAxis dataKey="title" type="category" width={150} stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '6px',
                  }}
                />
                <Bar dataKey="total_loans" fill="#f59e0b" name="Total Loans" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Hostel Analytics */}
        {hostelAnalytics && hostelAnalytics.success && hostelAnalytics.rows.length > 0 && (
          <div style={{ padding: '20px', backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}>
            <h3 style={{ marginBottom: '16px', fontSize: '16px', fontWeight: 600, color: 'hsl(var(--foreground))' }}>
              🏠 Hostel Occupancy Rates
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={hostelAnalytics.rows.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="hostel_name" stroke="hsl(var(--muted-foreground))" angle={-45} textAnchor="end" height={100} />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '6px',
                  }}
                />
                <Legend />
                <Bar dataKey="occupancy_rate" fill="#8b5cf6" name="Occupancy %" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

      </div>

      {/* Sync Status Section (Collapsed) */}
      <details style={{ marginTop: '32px', padding: '16px', backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}>
        <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: '16px', color: 'hsl(var(--foreground))' }}>
          🔄 Data Sync Status
        </summary>
        <div style={{ marginTop: '16px' }}>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <button
              onClick={loadSyncStatus}
              disabled={loading}
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                backgroundColor: 'hsl(var(--card))',
                color: 'hsl(var(--primary))',
                border: '1px solid hsl(var(--primary))',
                borderRadius: '6px',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1,
                transition: 'all 0.2s',
              }}
            >
              🔄 Refresh Status
            </button>
            <button
              onClick={handleSyncAll}
              disabled={syncing}
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                backgroundColor: 'hsl(var(--primary))',
                color: 'hsl(var(--primary-foreground))',
                border: 'none',
                borderRadius: '6px',
                cursor: syncing ? 'not-allowed' : 'pointer',
                opacity: syncing ? 0.6 : 1,
                transition: 'all 0.2s',
              }}
            >
              {syncing ? '⏳ Syncing...' : '🔄 Sync All Tables'}
            </button>
          </div>

          {syncStatus && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'hsl(var(--muted-foreground))', marginBottom: '4px' }}>
                    Synced Tables
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 600, color: '#10b981' }}>
                    {syncStatus.synced_tables.length}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'hsl(var(--muted-foreground))', marginBottom: '4px' }}>
                    Unsynced Tables
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 600, color: '#f59e0b' }}>
                    {syncStatus.unsynced_tables.length}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'hsl(var(--muted-foreground))', marginBottom: '4px' }}>
                    Out of Sync
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 600, color: '#ef4444' }}>
                    {syncStatus.table_stats.filter((t) => !t.in_sync).length}
                  </div>
                </div>
              </div>

              {syncStatus.table_stats.length > 0 && (
                <div style={{ marginTop: '16px', maxHeight: '200px', overflowY: 'auto' }}>
                  {syncStatus.table_stats.map((stat) => (
                    <div
                      key={stat.table}
                      style={{
                        padding: '8px 12px',
                        marginBottom: '4px',
                        backgroundColor: stat.in_sync ? 'hsl(var(--success) / 0.1)' : 'hsl(var(--destructive) / 0.1)',
                        borderLeft: `3px solid ${stat.in_sync ? '#10b981' : '#ef4444'}`,
                        borderRadius: '4px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        fontSize: '13px',
                      }}
                    >
                      <span style={{ fontWeight: 500 }}>{stat.table}</span>
                      <span style={{ color: 'hsl(var(--muted-foreground))' }}>
                        PG: {stat.pg_rows.toLocaleString()} | DuckDB: {stat.ch_rows.toLocaleString()}
                        {stat.in_sync ? ' ✅' : ' ⚠️'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
