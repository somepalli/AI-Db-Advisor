import { useState, useEffect } from 'react';
import { analyzeApi, optimizationApi } from '../api/client';
import type { SchemaResponse } from '../types';

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
    loadSchema();
  }, [dataSourceId]);

  const loadSchema = async () => {
    try {
      setLoading(true);
      const data = await analyzeApi.getSchema(dataSourceId);
      setSchema(data);
      setError(null);
    } catch (err) {
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
      const result = await optimizationApi.optimizeDatabase(dataSourceId);
      setOptimizationResult({ type: 'database', data: result });
    } catch (err) {
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
      const result = await optimizationApi.optimizeTable(dataSourceId, shortTableName);
      setOptimizationResult({ type: 'table', data: result });
    } catch (err) {
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

  if (loading) {
    return <div style={{ padding: '16px' }}>Loading schema...</div>;
  }

  if (error) {
    return <div style={{ padding: '16px', color: 'var(--error)' }}>{error}</div>;
  }

  const tables = schema?.tables || {};

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h3 style={{ margin: 0, fontSize: '16px' }}>Database Explorer</h3>
        <button
          onClick={handleOptimizeDatabase}
          disabled={optimizationLoading}
          style={{
            padding: '6px 12px',
            fontSize: '12px',
            backgroundColor: 'var(--primary)',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: optimizationLoading ? 'not-allowed' : 'pointer',
            opacity: optimizationLoading ? 0.6 : 1,
          }}
        >
          {optimizationLoading ? '⏳ Optimizing...' : '🚀 Optimize DB'}
        </button>
      </div>

      {Object.keys(tables).length === 0 ? (
        <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          No tables found
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {Object.entries(tables).map(([tableName, columns]) => (
            <div key={tableName} style={{ border: '1px solid var(--border-color)', borderRadius: '6px', overflow: 'hidden' }}>
              <div
                onClick={() => toggleTable(tableName)}
                style={{
                  padding: '12px',
                  backgroundColor: expandedTables.has(tableName) ? 'var(--bg-secondary)' : 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '14px',
                  fontWeight: 500,
                }}
              >
                <span>{expandedTables.has(tableName) ? '▼' : '▶'}</span>
                <span>📋 {tableName}</span>
                <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {columns.length} columns
                </span>
                <button
                  onClick={(e) => handleOptimizeTable(tableName, e)}
                  disabled={optimizationLoading}
                  style={{
                    padding: '4px 8px',
                    fontSize: '11px',
                    backgroundColor: '#10b981',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: optimizationLoading ? 'not-allowed' : 'pointer',
                    opacity: optimizationLoading ? 0.6 : 1,
                  }}
                  title={`Optimize ${tableName}`}
                >
                  ⚡ Optimize
                </button>
              </div>

              {expandedTables.has(tableName) && (
                <div style={{ borderTop: '1px solid var(--border-color)', padding: '8px' }}>
                  {columns.map((col, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '6px 12px',
                        fontSize: '13px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        borderBottom: idx < columns.length - 1 ? '1px solid var(--border-color)' : 'none',
                      }}
                    >
                      <span style={{ fontWeight: 500 }}>{col.column}</span>
                      <span style={{ color: 'var(--text-secondary)' }}>
                        {col.type} {col.nullable === 'YES' ? '(nullable)' : ''}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <button
        onClick={loadSchema}
        style={{
          marginTop: '16px',
          padding: '8px 16px',
          fontSize: '13px',
          backgroundColor: 'var(--primary)',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          cursor: 'pointer',
        }}
      >
        🔄 Refresh
      </button>

      {/* Optimization Results Panel */}
      {optimizationResult && (
        <div style={{
          marginTop: '16px',
          padding: '16px',
          border: '2px solid var(--primary)',
          borderRadius: '8px',
          backgroundColor: 'rgba(37, 99, 235, 0.05)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: 'var(--primary)' }}>
              {optimizationResult.type === 'database' ? '🚀 Database Optimization' : '⚡ Table Optimization'}
            </h4>
            <button
              onClick={() => setOptimizationResult(null)}
              style={{
                padding: '2px 8px',
                fontSize: '12px',
                backgroundColor: 'transparent',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              ✕ Close
            </button>
          </div>

          {optimizationResult.type === 'database' && (
            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Tables: {optimizationResult.data.table_count} | Indexes: {optimizationResult.data.index_count}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {optimizationResult.data.suggestions?.map((suggestion: any) => (
                  <div
                    key={suggestion.id}
                    style={{
                      padding: '10px',
                      backgroundColor: 'white',
                      borderLeft: `3px solid ${
                        suggestion.severity === 'high' ? 'var(--error)' :
                        suggestion.severity === 'medium' ? '#f59e0b' :
                        '#10b981'
                      }`,
                      borderRadius: '4px',
                      fontSize: '12px',
                      display: 'flex',
                      gap: '10px',
                    }}
                  >
                    {suggestion.executable && (
                      <input
                        type="checkbox"
                        checked={selectedSuggestions.has(suggestion.id)}
                        onChange={() => toggleSuggestion(suggestion.id)}
                        style={{ marginTop: '2px' }}
                      />
                    )}
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                        {suggestion.category.toUpperCase()}: {suggestion.summary}
                      </div>
                      <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                        {suggestion.details}
                      </div>
                      {suggestion.sql && (
                        <div style={{
                          marginTop: '6px',
                          padding: '6px',
                          backgroundColor: '#f3f4f6',
                          borderRadius: '4px',
                          fontFamily: 'monospace',
                          fontSize: '11px',
                          whiteSpace: 'pre-wrap',
                        }}>
                          {suggestion.sql}
                        </div>
                      )}
                      <div style={{ fontSize: '11px', color: 'var(--primary)', marginTop: '4px' }}>
                        💡 {suggestion.recommendation}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {optimizationResult.type === 'table' && (
            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Table: {optimizationResult.data.table} | Columns: {optimizationResult.data.column_count} | Indexes: {optimizationResult.data.index_count}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {optimizationResult.data.suggestions?.map((suggestion: any) => (
                  <div
                    key={suggestion.id}
                    style={{
                      padding: '10px',
                      backgroundColor: 'white',
                      borderLeft: `3px solid ${
                        suggestion.severity === 'high' ? 'var(--error)' :
                        suggestion.severity === 'medium' ? '#f59e0b' :
                        '#10b981'
                      }`,
                      borderRadius: '4px',
                      fontSize: '12px',
                      display: 'flex',
                      gap: '10px',
                    }}
                  >
                    {suggestion.executable && (
                      <input
                        type="checkbox"
                        checked={selectedSuggestions.has(suggestion.id)}
                        onChange={() => toggleSuggestion(suggestion.id)}
                        style={{ marginTop: '2px' }}
                      />
                    )}
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                        {suggestion.category.toUpperCase()}: {suggestion.summary}
                      </div>
                      <div style={{ color: 'var(--text-secondary)', marginBottom: '4px', whiteSpace: 'pre-wrap' }}>
                        {suggestion.details}
                      </div>
                      {suggestion.sql && (
                        <div style={{
                          marginTop: '6px',
                          padding: '6px',
                          backgroundColor: '#f3f4f6',
                          borderRadius: '4px',
                          fontFamily: 'monospace',
                          fontSize: '11px',
                          whiteSpace: 'pre-wrap',
                        }}>
                          {suggestion.sql}
                        </div>
                      )}
                      <div style={{ fontSize: '11px', color: 'var(--primary)', marginTop: '4px' }}>
                        💡 {suggestion.recommendation}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Apply Button */}
          {selectedSuggestions.size > 0 && (
            <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--border-color)' }}>
              <button
                onClick={handleApplySelected}
                disabled={applyLoading}
                style={{
                  padding: '8px 16px',
                  fontSize: '13px',
                  backgroundColor: '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: applyLoading ? 'not-allowed' : 'pointer',
                  opacity: applyLoading ? 0.6 : 1,
                  fontWeight: 600,
                }}
              >
                {applyLoading ? '⏳ Applying...' : `✅ Apply Selected (${selectedSuggestions.size})`}
              </button>
            </div>
          )}

          {/* Apply Results */}
          {applyResults && (
            <div style={{
              marginTop: '12px',
              padding: '12px',
              backgroundColor: applyResults.error_count > 0 ? '#fee2e2' : '#d1fae5',
              borderRadius: '6px',
            }}>
              <div style={{ fontWeight: 600, marginBottom: '8px', fontSize: '13px' }}>
                Apply Results: {applyResults.success_count} succeeded, {applyResults.error_count} failed
              </div>
              {applyResults.results?.map((result: any, idx: number) => (
                <div
                  key={idx}
                  style={{
                    padding: '6px',
                    marginBottom: '4px',
                    backgroundColor: 'white',
                    borderRadius: '4px',
                    fontSize: '11px',
                  }}
                >
                  <div style={{ color: result.status === 'success' ? '#10b981' : 'var(--error)', fontWeight: 600 }}>
                    {result.status === 'success' ? '✅' : '❌'} {result.message}
                  </div>
                  <div style={{ fontFamily: 'monospace', fontSize: '10px', marginTop: '2px', opacity: 0.7 }}>
                    {result.sql}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
