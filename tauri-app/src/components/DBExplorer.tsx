import { useState, useEffect } from 'react';
import { analyzeApi, optimizationApi } from '../api/client';
import type { SchemaResponse } from '../types';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from './ui/collapsible';
import { ChevronRight, Database, Zap, RefreshCw, X } from 'lucide-react';

interface Props {
  dataSourceId: string;
}

interface OptimizationResult {
  type: 'database' | 'table';
  data: any;
}

export function DBExplorer({ dataSourceId }: Props) {
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [optimizationResult, setOptimizationResult] = useState<OptimizationResult | null>(null);
  const [optimizationLoading, setOptimizationLoading] = useState(false);
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set());
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyResults, setApplyResults] = useState<any>(null);

  useEffect(() => {
    if (dataSourceId) {
      loadSchema();
    } else {
      setLoading(false);
      setSchema(null);
    }
  }, [dataSourceId]);

  const loadSchema = async () => {
    if (!dataSourceId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      console.log('📊 Loading schema for:', dataSourceId);
      const data = await analyzeApi.getSchema(dataSourceId);
      console.log('✅ Schema loaded:', Object.keys(data.tables || {}).length, 'tables');
      setSchema(data);
      setError(null);
    } catch (err) {
      console.error('❌ Schema load error:', err);
      setError('Failed to load schema: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const toggleTable = (tableName: string) => {
    const newExpanded = new Set(expandedTables);
    if (newExpanded.has(tableName)) {
      newExpanded.delete(tableName);
    } else {
      newExpanded.add(tableName);
    }
    setExpandedTables(newExpanded);
  };

  const handleOptimizeDatabase = async () => {
    try {
      setOptimizationLoading(true);
      setError(null);
      setSelectedSuggestions(new Set());
      setApplyResults(null);
      console.log('🚀 Optimizing database:', dataSourceId);
      const result = await optimizationApi.optimizeDatabase(dataSourceId);
      console.log('✅ Database optimization result:', result);
      setOptimizationResult({ type: 'database', data: result });
    } catch (err) {
      console.error('❌ Database optimization error:', err);
      setError('Failed to optimize database: ' + (err as Error).message);
    } finally {
      setOptimizationLoading(false);
    }
  };

  const handleOptimizeTable = async (tableName: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent table expansion/collapse
    try {
      setOptimizationLoading(true);
      setError(null);
      setSelectedSuggestions(new Set());
      setApplyResults(null);
      // Extract short table name (remove schema prefix if present)
      const shortTableName = tableName.split('.').pop() || tableName;
      console.log('🚀 Optimizing table:', tableName, '→', shortTableName);
      const result = await optimizationApi.optimizeTable(dataSourceId, shortTableName);
      console.log('✅ Table optimization result:', result);
      setOptimizationResult({ type: 'table', data: result });
    } catch (err) {
      console.error('❌ Table optimization error:', err);
      setError('Failed to optimize table: ' + (err as Error).message);
    } finally {
      setOptimizationLoading(false);
    }
  };

  const toggleSuggestion = (id: string) => {
    const newSelected = new Set(selectedSuggestions);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedSuggestions(newSelected);
  };

  const handleApplySelected = async () => {
    if (!optimizationResult) return;

    const suggestions = optimizationResult.data.suggestions || [];
    const sqlStatements = suggestions
      .filter((s: any) => selectedSuggestions.has(s.id) && s.executable && s.sql)
      .map((s: any) => s.sql);

    if (sqlStatements.length === 0) {
      setError('No executable SQL statements selected');
      return;
    }

    if (!confirm(`Apply ${sqlStatements.length} optimization(s)? This will execute SQL on your database.`)) {
      return;
    }

    try {
      setApplyLoading(true);
      setError(null);
      const result = await optimizationApi.applyOptimizations(dataSourceId, sqlStatements);
      setApplyResults(result);

      // Refresh schema after applying
      if (result.success_count > 0) {
        await loadSchema();
      }
    } catch (err) {
      setError('Failed to apply optimizations: ' + (err as Error).message);
    } finally {
      setApplyLoading(false);
    }
  };

  if (!dataSourceId) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-4 text-center">
        <Database className="h-12 w-12 text-muted-foreground mb-3" />
        <p className="text-sm text-muted-foreground">
          Select a connection to<br />explore database schema
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-4">
        <RefreshCw className="h-8 w-8 text-primary animate-spin mb-3" />
        <p className="text-sm text-muted-foreground">Loading schema...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md">
          {error}
        </div>
        <Button onClick={loadSchema} variant="outline" size="sm" className="w-full mt-3 text-xs">
          <RefreshCw className="h-3 w-3 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  const tables = schema?.tables || {};

  return (
    <ScrollArea className="h-full">
      <div className="p-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-sm font-semibold">Database Explorer</h3>
          <Button
            onClick={handleOptimizeDatabase}
            disabled={optimizationLoading}
            size="sm"
            className="text-xs h-7"
          >
            {optimizationLoading ? (
              <>
                <RefreshCw className="h-3 w-3 animate-spin" />
                Optimizing...
              </>
            ) : (
              <>
                <Database className="h-3 w-3" />
                Optimize DB
              </>
            )}
          </Button>
        </div>

        {Object.keys(tables).length === 0 ? (
          <div className="text-muted-foreground text-sm">No tables found</div>
        ) : (
          <div className="space-y-2">
            {Object.entries(tables).map(([tableName, columns]) => (
              <Collapsible
                key={tableName}
                open={expandedTables.has(tableName)}
                onOpenChange={() => toggleTable(tableName)}
              >
                <Card>
                  <CollapsibleTrigger className="w-full">
                    <CardContent className="p-3 flex items-center gap-2">
                      <ChevronRight
                        className={`h-4 w-4 transition-transform ${
                          expandedTables.has(tableName) ? 'rotate-90' : ''
                        }`}
                      />
                      <Database className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium flex-1 text-left">{tableName}</span>
                      <Badge variant="outline" className="text-xs">
                        {columns.length} columns
                      </Badge>
                      <Button
                        onClick={(e) => handleOptimizeTable(tableName, e)}
                        disabled={optimizationLoading}
                        size="sm"
                        variant="default"
                        className="text-xs h-6 ml-2"
                      >
                        <Zap className="h-3 w-3" />
                        Optimize
                      </Button>
                    </CardContent>
                  </CollapsibleTrigger>

                  <CollapsibleContent>
                    <div className="border-t">
                      {columns.map((col, idx) => (
                        <div
                          key={idx}
                          className={`px-3 py-2 flex justify-between text-sm ${
                            idx < columns.length - 1 ? 'border-b' : ''
                          }`}
                        >
                          <span className="font-medium">{col.column}</span>
                          <span className="text-muted-foreground text-xs">
                            {col.type} {col.nullable === 'YES' ? '(nullable)' : ''}
                          </span>
                        </div>
                      ))}
                    </div>
                  </CollapsibleContent>
                </Card>
              </Collapsible>
            ))}
          </div>
        )}

        <Button
          onClick={loadSchema}
          variant="outline"
          size="sm"
          className="w-full mt-4 text-xs"
        >
          <RefreshCw className="h-3 w-3" />
          Refresh
        </Button>

        {/* Optimization Results Panel */}
        {optimizationResult && (
          <Card className="mt-4 border-2 border-primary bg-primary/5">
            <CardContent className="p-4">
              <div className="flex justify-between items-center mb-3">
                <h4 className="text-sm font-semibold text-primary flex items-center gap-2">
                  {optimizationResult.type === 'database' ? (
                    <>
                      <Database className="h-4 w-4" />
                      Database Optimization
                    </>
                  ) : (
                    <>
                      <Zap className="h-4 w-4" />
                      Table Optimization
                    </>
                  )}
                </h4>
                <Button
                  onClick={() => setOptimizationResult(null)}
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {optimizationResult.type === 'database' && (
                <div>
                  <div className="text-xs text-muted-foreground mb-2">
                    Tables: {optimizationResult.data.table_count} | Indexes: {optimizationResult.data.index_count}
                  </div>
                  <div className="space-y-2">
                    {optimizationResult.data.suggestions?.map((suggestion: any) => {
                      const severityColor = suggestion.severity === 'high' ? 'border-l-destructive' :
                                           suggestion.severity === 'medium' ? 'border-l-warning' :
                                           'border-l-primary';
                      return (
                        <Card key={suggestion.id} className={`border-l-4 ${severityColor}`}>
                          <CardContent className="p-3 flex gap-3 items-start">
                            {suggestion.executable && (
                              <input
                                type="checkbox"
                                checked={selectedSuggestions.has(suggestion.id)}
                                onChange={() => toggleSuggestion(suggestion.id)}
                                className="mt-1"
                              />
                            )}
                            <div className="flex-1 space-y-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold">
                                  {suggestion.category.toUpperCase()}: {suggestion.summary}
                                </span>
                                <Badge variant={suggestion.severity === 'high' ? 'destructive' : suggestion.severity === 'medium' ? 'warning' : 'default'} className="text-xs">
                                  {suggestion.severity}
                                </Badge>
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {suggestion.details}
                              </div>
                              {suggestion.sql && (
                                <pre className="text-[10px] p-2 bg-muted rounded font-mono whitespace-pre-wrap">
                                  {suggestion.sql}
                                </pre>
                              )}
                              <div className="text-xs text-primary">
                                {suggestion.recommendation}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </div>
              )}

              {optimizationResult.type === 'table' && (
                <div>
                  <div className="text-xs text-muted-foreground mb-2">
                    Table: {optimizationResult.data.table} | Columns: {optimizationResult.data.column_count} | Indexes: {optimizationResult.data.index_count}
                  </div>
                  <div className="space-y-2">
                    {optimizationResult.data.suggestions?.map((suggestion: any) => {
                      const severityColor = suggestion.severity === 'high' ? 'border-l-destructive' :
                                           suggestion.severity === 'medium' ? 'border-l-warning' :
                                           'border-l-primary';
                      return (
                        <Card key={suggestion.id} className={`border-l-4 ${severityColor}`}>
                          <CardContent className="p-3 flex gap-3 items-start">
                            {suggestion.executable && (
                              <input
                                type="checkbox"
                                checked={selectedSuggestions.has(suggestion.id)}
                                onChange={() => toggleSuggestion(suggestion.id)}
                                className="mt-1"
                              />
                            )}
                            <div className="flex-1 space-y-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold">
                                  {suggestion.category.toUpperCase()}: {suggestion.summary}
                                </span>
                                <Badge variant={suggestion.severity === 'high' ? 'destructive' : suggestion.severity === 'medium' ? 'warning' : 'default'} className="text-xs">
                                  {suggestion.severity}
                                </Badge>
                              </div>
                              <div className="text-xs text-muted-foreground whitespace-pre-wrap">
                                {suggestion.details}
                              </div>
                              {suggestion.sql && (
                                <pre className="text-[10px] p-2 bg-muted rounded font-mono whitespace-pre-wrap">
                                  {suggestion.sql}
                                </pre>
                              )}
                              <div className="text-xs text-primary">
                                {suggestion.recommendation}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Apply Button */}
              {selectedSuggestions.size > 0 && (
                <div className="mt-3 pt-3 border-t">
                  <Button
                    onClick={handleApplySelected}
                    disabled={applyLoading}
                    className="w-full text-xs"
                    size="sm"
                  >
                    {applyLoading ? (
                      <>
                        <RefreshCw className="h-3 w-3 animate-spin" />
                        Applying...
                      </>
                    ) : (
                      `Apply Selected (${selectedSuggestions.size})`
                    )}
                  </Button>
                </div>
              )}

              {/* Apply Results */}
              {applyResults && (
                <Card className={`mt-3 ${applyResults.error_count > 0 ? 'bg-destructive/10' : 'bg-primary/10'}`}>
                  <CardContent className="p-3">
                    <div className="text-sm font-semibold mb-2">
                      Apply Results: {applyResults.success_count} succeeded, {applyResults.error_count} failed
                    </div>
                    <div className="space-y-2">
                      {applyResults.results?.map((result: any, idx: number) => (
                        <Card key={idx}>
                          <CardContent className="p-2">
                            <div className={`text-xs font-semibold ${result.status === 'success' ? 'text-primary' : 'text-destructive'}`}>
                              {result.message}
                            </div>
                            <div className="font-mono text-[10px] mt-1 text-muted-foreground">
                              {result.sql}
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </ScrollArea>
  );
}
