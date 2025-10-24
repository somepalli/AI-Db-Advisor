import { useState, useEffect } from 'react';
import { datasourcesApi } from '../api/client';
import { connectionStore } from '../utils/store';
import type { DataSource, DataSourceCreate } from '../types';

interface Props {
  onSelectDataSource: (dsId: string) => void;
}

export function DataSourceManager({ onSelectDataSource }: Props) {
  const [dataSources, setDataSources] = useState<Record<string, DataSource>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<DataSourceCreate>({
    id: '',
    engine: 'postgres',
    dsn: '',
  });

  useEffect(() => {
    loadDataSources();
  }, []);

  const loadDataSources = async () => {
    try {
      setLoading(true);

      // First, load saved connections from local storage
      const savedConnections = connectionStore.getAll();

      // Try to register each saved connection with the backend
      for (const conn of savedConnections) {
        try {
          await datasourcesApi.create({
            id: conn.id,
            engine: conn.engine,
            dsn: conn.dsn,
          });
        } catch (err) {
          // Connection might already exist, which is fine
          console.log(`Connection ${conn.id} already registered or failed to register`);
        }
      }

      // Now load all data sources from backend
      const data = await datasourcesApi.list();
      setDataSources(data);
      setError(null);
    } catch (err) {
      setError('Failed to load data sources: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Create in backend
      await datasourcesApi.create(formData);

      // Save to local storage for persistence
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

  if (loading) {
    return <div className="loading">Loading data sources...</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h2>Data Sources</h2>
        <p>Manage your database connections</p>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h3>Registered Data Sources ({Object.keys(dataSources).length})</h3>
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? 'Cancel' : '+ Add Data Source'}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} style={{ marginBottom: '24px', padding: '20px', backgroundColor: 'var(--bg-secondary)', borderRadius: '8px' }}>
            <div className="form-group">
              <label>ID</label>
              <input
                type="text"
                value={formData.id}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                placeholder="my-postgres-db"
                required
              />
            </div>
            <div className="form-group">
              <label>Engine</label>
              <select
                value={formData.engine}
                onChange={(e) => setFormData({ ...formData, engine: e.target.value })}
              >
                <option value="postgres">PostgreSQL</option>
              </select>
            </div>
            <div className="form-group">
              <label>DSN (Connection String)</label>
              <input
                type="text"
                value={formData.dsn}
                onChange={(e) => setFormData({ ...formData, dsn: e.target.value })}
                placeholder="postgresql://user:password@localhost:5432/dbname"
                required
              />
            </div>
            <button type="submit" className="btn btn-primary">Create Data Source</button>
          </form>
        )}

        {Object.keys(dataSources).length === 0 ? (
          <div className="empty-state">
            <h3>No Data Sources</h3>
            <p>Add your first database connection to get started</p>
          </div>
        ) : (
          <div className="datasource-list">
            {Object.entries(dataSources).map(([id, ds]) => (
              <div
                key={id}
                className="datasource-item"
                onClick={() => onSelectDataSource(id)}
              >
                <h4>{id}</h4>
                <p><strong>Engine:</strong> {ds.engine}</p>
                <p><strong>DSN:</strong> {ds.dsn ? ds.dsn.substring(0, 50) + '...' : 'N/A'}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
