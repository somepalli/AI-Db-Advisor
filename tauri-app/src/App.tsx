import { useState, useEffect } from 'react';
import { Database } from 'lucide-react';
import { ConnectionPanel } from './components/ConnectionPanel';
import { SQLEditorWithAutocomplete } from './components/SQLEditorWithAutocomplete';
import { AIAssistant } from './components/AIAssistant';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';
import AlertPanel from './components/AlertPanel';
import { AlertRulesPanel } from './components/AlertRulesPanel';
import { AgentPanel } from './components/AgentPanel';
import { Separator } from './components/ui/separator';
import { LLMStatusBadge } from './components/LLMStatusBadge';
import { OptimizationProvider } from './lib/optimizationContext';
import { datasourcesApi, type DataSource } from './api/client';

type ViewType = 'query' | 'analytics' | 'alerts' | 'agent';

function App() {
  const [selectedDataSource, setSelectedDataSource] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<ViewType>('query');
  const [pgDataSource, setPgDataSource] = useState<string>('');
  const [chDataSource, setChDataSource] = useState<string>('');
  const [datasources, setDatasources] = useState<Record<string, DataSource>>({});
  const [loadingDatasources, setLoadingDatasources] = useState(false);

  // Track which views have ever been activated so we can lazy-mount them.
  // Once mounted, a view is NEVER unmounted — only hidden with CSS.
  // This prevents the re-initialization loading flash and preserves in-flight
  // scan state in AgentPanel when the user navigates to another tab.
  const [mountedViews, setMountedViews] = useState<Set<ViewType>>(new Set<ViewType>(['query']));

  const switchView = (view: ViewType) => {
    setCurrentView(view);
    setMountedViews((prev) => {
      if (prev.has(view)) return prev;
      return new Set([...prev, view]);
    });
  };

  // Load datasources for Analytics dropdown (only on first activation).
  useEffect(() => {
    if (currentView === 'analytics' && Object.keys(datasources).length === 0) {
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
    <OptimizationProvider>
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
          {(
            [
              { id: 'query',     label: 'Query Analyzer' },
              { id: 'analytics', label: '📊 Analytics' },
              { id: 'alerts',    label: '🔔 Alerts' },
              { id: 'agent',     label: '🤖 Agent' },
            ] as const
          ).map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => switchView(id)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                currentView === id
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <LLMStatusBadge />
          <div className="text-xs text-muted-foreground hidden lg:block">
            Professional Database Management & AI Optimization
          </div>
        </div>
      </header>

      {/* Main Content — all views are lazy-mounted once visited, then kept mounted.
           Only the active view is visible (display != none). This prevents the
           re-initialisation loading flash and preserves in-flight scan state when
           switching away from the Agent tab and back. */}

      {/* ── Query Analyzer ── */}
      <div
        className="flex-1 flex overflow-hidden"
        style={{ display: currentView === 'query' ? undefined : 'none' }}
      >
        {mountedViews.has('query') && (
          <>
            <div className="w-96 border-r border-border flex flex-col bg-card">
              <ConnectionPanel
                onSelectDataSource={handleSelectDataSource}
                selectedDataSource={selectedDataSource}
              />
            </div>

            <Separator orientation="vertical" />

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

            <div className="w-[34rem] border-l border-border flex flex-col bg-card">
              <AIAssistant dataSourceId={selectedDataSource} />
            </div>
          </>
        )}
      </div>

      {/* ── Analytics ── */}
      <div
        className="flex-1 flex flex-col overflow-hidden"
        style={{ display: currentView === 'analytics' ? undefined : 'none' }}
      >
        {mountedViews.has('analytics') && (
          pgDataSource && chDataSource ? (
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
                          <option key={id} value={id}>{id} ({ds.engine})</option>
                        ))}
                      </select>
                      {pgDatasources.length === 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          No PostgreSQL datasources found. Add one in Query Analyzer first.
                        </p>
                      )}
                    </div>

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
                          <option key={id} value={id}>{id} ({ds.engine})</option>
                        ))}
                      </select>
                      {duckdbDatasources.length === 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          No DuckDB datasources found. Add one in Query Analyzer first.
                        </p>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => pgDataSource && chDataSource && switchView('analytics')}
                      disabled={!pgDataSource || !chDataSource}
                      className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Load Analytics Dashboard
                    </button>

                    <button
                      type="button"
                      onClick={loadDatasources}
                      className="w-full px-4 py-2 border border-border rounded-lg font-medium hover:bg-muted transition-colors"
                    >
                      🔄 Refresh Datasources
                    </button>
                  </div>
                )}
              </div>
            </div>
          )
        )}
      </div>

      {/* ── Alerts ── */}
      <div
        className="flex-1 overflow-auto bg-background"
        style={{ display: currentView === 'alerts' ? undefined : 'none' }}
      >
        {mountedViews.has('alerts') && (
          <>
            <AlertPanel />
            <AlertRulesPanel dataSourceId={selectedDataSource} />
          </>
        )}
      </div>

      {/* ── Agent ── */}
      <div
        className="flex-1 overflow-auto bg-background"
        style={{ display: currentView === 'agent' ? undefined : 'none' }}
      >
        {mountedViews.has('agent') && <AgentPanel />}
      </div>
    </div>
    </OptimizationProvider>
  );
}

export default App;
