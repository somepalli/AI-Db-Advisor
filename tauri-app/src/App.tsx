import { useState, useEffect } from 'react';
import { Database } from 'lucide-react';
import { ConnectionPanel } from './components/ConnectionPanel';
import { DBExplorer } from './components/DBExplorer';
import { SQLEditorWithAutocomplete } from './components/SQLEditorWithAutocomplete';
import { AIAssistant } from './components/AIAssistant';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';
import AlertPanel from './components/AlertPanel';
import { Separator } from './components/ui/separator';
import { datasourcesApi, type DataSource } from './api/client';

type ViewType = 'query' | 'analytics' | 'alerts';

function App() {
  const [selectedDataSource, setSelectedDataSource] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<ViewType>('query');
  const [pgDataSource, setPgDataSource] = useState<string>('');
  const [chDataSource, setChDataSource] = useState<string>('');
  const [datasources, setDatasources] = useState<Record<string, DataSource>>({});
  const [loadingDatasources, setLoadingDatasources] = useState(false);

  // Load datasources for Analytics dropdown
  useEffect(() => {
    if (currentView === 'analytics') {
      loadDatasources();
    }
  }, [currentView]);

  const loadDatasources = async () => {
    setLoadingDatasources(true);
    try {
      const data = await datasourcesApi.list();
      setDatasources(data);
    } catch (err) {
      console.error('Failed to load datasources:', err);
    } finally {
      setLoadingDatasources(false);
    }
  };

  // Filter datasources by engine type
  const pgDatasources = Object.entries(datasources).filter(
    ([_, ds]) => ['postgres', 'postgresql', 'pg'].includes(ds.engine.toLowerCase())
  );
  const duckdbDatasources = Object.entries(datasources).filter(
    ([_, ds]) => ds.engine.toLowerCase() === 'duckdb'
  );

  const handleSelectDataSource = (dsId: string) => {
    setSelectedDataSource(dsId);
  };

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      {/* Header */}
      <header className="h-14 border-b border-border bg-card px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Database className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-lg font-semibold">AI DB Advisor</h1>
        </div>

        {/* View Toggle Buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => setCurrentView('query')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              currentView === 'query'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            Query Analyzer
          </button>
          <button
            onClick={() => setCurrentView('analytics')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              currentView === 'analytics'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            📊 Analytics
          </button>
          <button
            onClick={() => setCurrentView('alerts')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              currentView === 'alerts'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            🔔 Alerts
          </button>
        </div>

        <div className="text-xs text-muted-foreground">
          Professional Database Management & AI Optimization
        </div>
      </header>

      {/* Main Content */}
      {currentView === 'alerts' ? (
        /* Alerts View */
        <div className="flex-1 overflow-auto bg-background">
          <AlertPanel />
        </div>
      ) : currentView === 'query' ? (
        <div className="flex-1 flex overflow-hidden">
          {/* Column 1: Connection Manager */}
          <div className="w-80 border-r border-border flex flex-col bg-card">
            <ConnectionPanel
              onSelectDataSource={handleSelectDataSource}
              selectedDataSource={selectedDataSource}
            />
          </div>

          <Separator orientation="vertical" />

          {/* Column 2: Database Explorer */}
          <div className="w-80 border-r border-border flex flex-col bg-card">
            <DBExplorer dataSourceId={selectedDataSource} />
          </div>

          <Separator orientation="vertical" />

          {/* Column 3: SQL Editor */}
          <div className="flex-1 flex flex-col bg-background">
            {selectedDataSource ? (
              <SQLEditorWithAutocomplete dataSourceId={selectedDataSource} />
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <Database className="h-16 w-16 mx-auto mb-4 text-muted-foreground" />
                  <h2 className="text-lg font-semibold mb-2">SQL Editor</h2>
                  <p className="text-sm text-muted-foreground">
                    Select a connection to start writing queries
                  </p>
                </div>
              </div>
            )}
          </div>

          <Separator orientation="vertical" />

          {/* Column 4: AI Assistant */}
          <div className="w-96 border-l border-border flex flex-col bg-card">
            <AIAssistant dataSourceId={selectedDataSource} />
          </div>
        </div>
      ) : (
        /* Analytics View */
        <div className="flex-1 flex flex-col overflow-hidden">
          {pgDataSource && chDataSource ? (
            <AnalyticsDashboard
              pgDataSourceId={pgDataSource}
              chDataSourceId={chDataSource}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center p-8 bg-background">
              <div className="max-w-md w-full">
                <h2 className="text-2xl font-bold mb-4">📊 Analytics Dashboard</h2>
                <p className="text-muted-foreground mb-6">
                  Select your PostgreSQL source database and DuckDB analytics database from existing connections.
                </p>

                {loadingDatasources ? (
                  <div className="text-center py-8">
                    <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto mb-2"></div>
                    <p className="text-sm text-muted-foreground">Loading datasources...</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* PostgreSQL Datasource Dropdown */}
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        PostgreSQL Source Database
                      </label>
                      <select
                        value={pgDataSource}
                        onChange={(e) => setPgDataSource(e.target.value)}
                        className="w-full px-3 py-2 border border-border rounded-lg bg-card text-foreground focus:ring-2 focus:ring-primary focus:border-transparent"
                      >
                        <option value="">Select PostgreSQL datasource...</option>
                        {pgDatasources.map(([id, ds]) => (
                          <option key={id} value={id}>
                            {id} ({ds.engine})
                          </option>
                        ))}
                      </select>
                      {pgDatasources.length === 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          No PostgreSQL datasources found. Add one in Query Analyzer first.
                        </p>
                      )}
                    </div>

                    {/* DuckDB Datasource Dropdown */}
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        DuckDB Analytics Database
                      </label>
                      <select
                        value={chDataSource}
                        onChange={(e) => setChDataSource(e.target.value)}
                        className="w-full px-3 py-2 border border-border rounded-lg bg-card text-foreground focus:ring-2 focus:ring-primary focus:border-transparent"
                      >
                        <option value="">Select DuckDB datasource...</option>
                        {duckdbDatasources.map(([id, ds]) => (
                          <option key={id} value={id}>
                            {id} ({ds.engine})
                          </option>
                        ))}
                      </select>
                      {duckdbDatasources.length === 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          No DuckDB datasources found. Add one in Query Analyzer first.
                        </p>
                      )}
                    </div>

                    <button
                      onClick={() => {
                        if (pgDataSource && chDataSource) {
                          // Trigger re-render
                          setCurrentView('analytics');
                        }
                      }}
                      disabled={!pgDataSource || !chDataSource}
                      className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Load Analytics Dashboard
                    </button>

                    <button
                      onClick={loadDatasources}
                      className="w-full px-4 py-2 border border-border rounded-lg font-medium hover:bg-muted transition-colors"
                    >
                      🔄 Refresh Datasources
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
