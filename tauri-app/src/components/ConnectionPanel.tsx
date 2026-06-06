import { useState, useEffect } from 'react';
import { datasourcesApi, analyzeApi } from '../api/client';
import { connectionStore } from '../utils/store';
import type { DataSource, Lock, Stats, TopQuery } from '../types';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Plus, Trash2, RefreshCw, ChevronDown } from 'lucide-react';
import {
  FEATURED_ENGINES,
  OTHER_ENGINES,
  getEngineDef,
  initialValues,
  EngineLogo,
} from '../lib/dbEngines';

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
  // Structured connection form: pick an engine, then fill host/port/etc. — the
  // DSN is assembled from these fields so users never type a raw connection string.
  const [engine, setEngine] = useState('postgres');
  const [connId, setConnId] = useState('');
  const [fieldValues, setFieldValues] = useState<Record<string, string>>(initialValues('postgres'));

  const selectEngine = (value: string) => {
    setEngine(value);
    setFieldValues(initialValues(value));
  };

  const resetForm = () => {
    setEngine('postgres');
    setConnId('');
    setFieldValues(initialValues('postgres'));
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
      const savedConnections = await connectionStore.getAll();

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
    const def = getEngineDef(engine);
    if (!def) {
      setError(`Unsupported engine: ${engine}`);
      return;
    }
    const dsn = def.buildDsn(fieldValues);
    try {
      await datasourcesApi.create({ id: connId, engine: def.value, dsn });
      await connectionStore.save({ id: connId, engine: def.value, dsn });

      setShowForm(false);
      resetForm();
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
      await connectionStore.delete(dsId);

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
    return <div className="p-4 text-sm text-muted-foreground">Loading...</div>;
  }

  const currentDef = getEngineDef(engine);
  const isOther = OTHER_ENGINES.some((e) => e.value === engine);

  return (
    <div className="h-full flex flex-col">
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as Tab)} className="flex-1 flex flex-col">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="connections" className="text-xs">Connections</TabsTrigger>
          <TabsTrigger value="stats" disabled={!selectedDataSource} className="text-xs">Stats</TabsTrigger>
          <TabsTrigger value="locks" disabled={!selectedDataSource} className="text-xs">Locks</TabsTrigger>
          <TabsTrigger value="queries" disabled={!selectedDataSource} className="text-xs">Queries</TabsTrigger>
        </TabsList>

        <div className="flex-1 overflow-y-auto p-4">
          {error && (
            <div className="bg-destructive/10 text-destructive text-xs p-3 rounded-md mb-3">
              {error}
            </div>
          )}

          <TabsContent value="connections" className="mt-0">
            <div className="flex justify-between items-center mb-3">
              <h4 className="text-sm font-semibold">Data Sources</h4>
              <Dialog
                open={showForm}
                onOpenChange={(open) => {
                  setShowForm(open);
                  if (!open) resetForm();
                }}
              >
                <DialogTrigger asChild>
                  <Button size="sm" className="text-xs h-7">
                    <Plus className="h-3 w-3" />
                    Add
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add Data Source</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleSubmit}>
                    <div className="space-y-3">
                      {/* Engine picker: top-5 logos + an "Other" tile that reveals a dropdown */}
                      <div>
                        <Label className="text-xs">Database</Label>
                        <div className="grid grid-cols-3 gap-2 mt-1">
                          {FEATURED_ENGINES.map((eng) => {
                            const active = engine === eng.value;
                            return (
                              <button
                                key={eng.value}
                                type="button"
                                onClick={() => selectEngine(eng.value)}
                                title={eng.label}
                                className={`flex flex-col items-center justify-center gap-1 rounded-md border p-2 h-16 transition-colors ${
                                  active
                                    ? 'border-primary border-2 bg-primary/5'
                                    : 'border-border hover:bg-accent'
                                }`}
                              >
                                <EngineLogo engine={eng.value} size={22} />
                                <span className="text-[10px] leading-tight text-center">
                                  {eng.label}
                                </span>
                              </button>
                            );
                          })}
                          {/* "Other" tile */}
                          <button
                            type="button"
                            onClick={() => {
                              if (!isOther) selectEngine(OTHER_ENGINES[0].value);
                            }}
                            title="Other databases"
                            className={`flex flex-col items-center justify-center gap-1 rounded-md border p-2 h-16 transition-colors ${
                              isOther
                                ? 'border-primary border-2 bg-primary/5'
                                : 'border-border hover:bg-accent'
                            }`}
                          >
                            {isOther ? (
                              <EngineLogo engine={engine} size={22} />
                            ) : (
                              <ChevronDown className="h-5 w-5 text-muted-foreground" />
                            )}
                            <span className="text-[10px] leading-tight text-center">
                              {isOther ? currentDef?.label : 'Other'}
                            </span>
                          </button>
                        </div>

                        {isOther && (
                          <Select value={engine} onValueChange={selectEngine}>
                            <SelectTrigger className="text-xs h-8 mt-2">
                              <SelectValue placeholder="Select database" />
                            </SelectTrigger>
                            <SelectContent>
                              {OTHER_ENGINES.map((eng) => (
                                <SelectItem key={eng.value} value={eng.value} className="text-xs">
                                  {eng.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      </div>

                      {/* Connection name */}
                      <div>
                        <Label htmlFor="conn-id" className="text-xs">Connection name</Label>
                        <Input
                          id="conn-id"
                          type="text"
                          value={connId}
                          onChange={(e) => setConnId(e.target.value)}
                          placeholder={`my-${currentDef?.value ?? 'db'}`}
                          required
                          className="text-xs h-8"
                        />
                      </div>

                      {/* Engine-specific credential fields */}
                      <div className="grid grid-cols-2 gap-2">
                        {currentDef?.fields.map((field) => {
                          const fullWidth = field.key === 'file' || field.key === 'database';
                          return (
                            <div key={field.key} className={fullWidth ? 'col-span-2' : ''}>
                              <Label htmlFor={`f-${field.key}`} className="text-xs">
                                {field.label}
                                {field.required && <span className="text-destructive"> *</span>}
                              </Label>
                              <Input
                                id={`f-${field.key}`}
                                type={field.type ?? 'text'}
                                value={fieldValues[field.key] ?? ''}
                                onChange={(e) =>
                                  setFieldValues({ ...fieldValues, [field.key]: e.target.value })
                                }
                                placeholder={field.placeholder}
                                required={field.required}
                                autoComplete="off"
                                className="text-xs h-8"
                              />
                            </div>
                          );
                        })}
                      </div>
                    </div>
                    <DialogFooter>
                      <Button type="submit" size="sm" className="text-xs">Create</Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </div>

            <div className="flex flex-col gap-2">
              {Object.keys(dataSources).length === 0 ? (
                <div className="text-center p-5 text-muted-foreground text-xs">
                  No connections
                </div>
              ) : (
                Object.entries(dataSources).map(([id, ds]) => (
                  <Card
                    key={id}
                    className={`cursor-pointer transition-colors ${
                      selectedDataSource === id ? 'border-primary border-2 bg-primary/5' : ''
                    }`}
                    onClick={() => onSelectDataSource(id)}
                  >
                    <CardContent className="p-3 flex justify-between items-center">
                      <div className="flex items-center gap-2 flex-1">
                        <EngineLogo engine={ds.engine} size={18} />
                        <div>
                          <div className="text-sm font-semibold">{id}</div>
                          <div className="text-xs text-muted-foreground">
                            {getEngineDef(ds.engine)?.label ?? ds.engine}
                          </div>
                        </div>
                        {selectedDataSource === id && (
                          <Badge variant="default" className="ml-2 text-xs">
                            <div className="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                            Connected
                          </Badge>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={(e) => handleDelete(id, e)}
                        title={`Delete ${id}`}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </TabsContent>

          <TabsContent value="stats" className="mt-0">
            {dashboardLoading ? (
              <div className="text-muted-foreground text-xs">Loading stats...</div>
            ) : stats ? (
              <div className="space-y-3">
                <Card>
                  <CardHeader className="p-3">
                    <CardTitle className="text-xs text-muted-foreground font-normal">Database Size</CardTitle>
                  </CardHeader>
                  <CardContent className="p-3 pt-0">
                    <div className="text-xl font-semibold text-primary">{formatBytes(stats.total_db_size)}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="p-3">
                    <CardTitle className="text-xs text-muted-foreground font-normal">Active Backends</CardTitle>
                  </CardHeader>
                  <CardContent className="p-3 pt-0">
                    <div className="text-xl font-semibold text-primary">{stats.active_backends}</div>
                  </CardContent>
                </Card>
                <Button variant="outline" size="sm" onClick={loadDashboardData} className="w-full text-xs">
                  <RefreshCw className="h-3 w-3" />
                  Refresh
                </Button>
              </div>
            ) : (
              <div className="text-muted-foreground text-xs">No stats available</div>
            )}
          </TabsContent>

          <TabsContent value="locks" className="mt-0">
            {dashboardLoading ? (
              <div className="text-muted-foreground text-xs">Loading locks...</div>
            ) : (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h4 className="text-sm font-semibold">Active Locks ({locks.length})</h4>
                  <Button variant="outline" size="icon" className="h-7 w-7" onClick={loadDashboardData}>
                    <RefreshCw className="h-3 w-3" />
                  </Button>
                </div>

                {locks.length === 0 ? (
                  <div className="text-primary text-xs p-3 text-center">
                    No active locks
                  </div>
                ) : (
                  <div className="space-y-2">
                    {locks.map((lock, idx) => (
                      <Card key={idx}>
                        <CardContent className="p-3">
                          <div className="text-xs font-semibold mb-2">{lock.locktype}</div>
                          <div className="text-xs text-muted-foreground space-y-1">
                            <div>Mode: {lock.mode}</div>
                            <div className="flex items-center gap-2">
                              <span>PID: {lock.pid}</span>
                              <Badge variant={lock.granted ? "default" : "destructive"} className="text-xs">
                                {lock.granted ? 'Granted' : 'Waiting'}
                              </Badge>
                            </div>
                            <div>Age: {lock.age}</div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}
          </TabsContent>

          <TabsContent value="queries" className="mt-0">
            {dashboardLoading ? (
              <div className="text-muted-foreground text-xs">Loading queries...</div>
            ) : (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h4 className="text-sm font-semibold">Top Queries ({topQueries.length})</h4>
                  <Button variant="outline" size="icon" className="h-7 w-7" onClick={loadDashboardData}>
                    <RefreshCw className="h-3 w-3" />
                  </Button>
                </div>

                {topQueries.length === 0 ? (
                  <div className="text-muted-foreground text-xs p-3 text-center">
                    No query statistics available
                  </div>
                ) : (
                  <div className="space-y-2">
                    {topQueries.map((query, idx) => (
                      <Card key={idx}>
                        <CardContent className="p-3">
                          <div className="text-xs font-semibold mb-2 text-primary">
                            #{idx + 1}
                          </div>
                          <div
                            className="font-mono text-[10px] mb-2 overflow-hidden text-ellipsis whitespace-nowrap bg-muted p-2 rounded"
                            title={query.query}
                          >
                            {query.query}
                          </div>
                          <div className="flex gap-3 text-[10px] text-muted-foreground">
                            <span>Calls: {query.calls}</span>
                            <span>Avg: {query.mean_time_ms.toFixed(2)}ms</span>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
