import { useState, useEffect } from 'react';
import { suggestionsApi } from '../api/client';
import type { Suggestion, ApplyResult, ApplyHistoryItem } from '../types/suggestions';
import { SuggestionCard } from './SuggestionCard';
import { useLocalStorage, useApplyHistory } from '../hooks/useLocalStorage';

interface Props {
  dsId: string;
}

export function OptimizerConsole({ dsId }: Props) {
  // Persistent settings
  const [sql, setSql] = useLocalStorage('optimizer_sql', '');
  const [includeAI, setIncludeAI] = useLocalStorage('optimizer_include_ai', true);
  const [topK, setTopK] = useLocalStorage('optimizer_top_k', 12);
  const [dryRun, setDryRun] = useLocalStorage('optimizer_dry_run', false);

  // State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // History
  const { history, addToHistory, clearHistory } = useApplyHistory();

  // Toast for results
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Grouped suggestions
  const groupedSuggestions = {
    query: suggestions.filter((s) => s.level === 'query'),
    table: suggestions.filter((s) => s.level === 'table'),
    db: suggestions.filter((s) => s.level === 'db'),
  };

  // Keyboard shortcut: Cmd/Ctrl+Enter
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleAnalyze();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [sql, dsId, includeAI, topK]);

  const handleAnalyze = async () => {
    if (!sql.trim()) {
      setError('Please enter a SQL query');
      return;
    }

    setLoading(true);
    setError(null);
    setNotes([]);
    setSuggestions([]);
    setSelectedIds(new Set());

    try {
      const response = await suggestionsApi.analyze({
        ds_id: dsId,
        sql,
        include_ai: includeAI,
        top_k: topK,
      });

      setSuggestions(response.suggestions);
      setNotes(response.notes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSelect = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleApplySingle = async (id: string) => {
    await applySelected([id]);
  };

  const handleApplySelected = async () => {
    if (selectedIds.size === 0) {
      showToast('No suggestions selected', 'error');
      return;
    }
    await applySelected(Array.from(selectedIds));
  };

  const applySelected = async (ids: string[]) => {
    try {
      // Prefer the ID-based endpoint: the backend resolves suggestions it persisted
      // during analysis, so we don't resend full payloads.
      const response = await suggestionsApi.apply({
        ds_id: dsId,
        suggestion_ids: ids,
        dry_run: dryRun,
      });

      // If the server couldn't resolve some IDs (e.g. the TTL store expired),
      // fall back to apply_direct for just those, sending the full objects.
      const missingIds = response.results
        .filter(
          (r) =>
            r.status === 'skipped' && /not found|expired|not yet implemented/i.test(r.message)
        )
        .map((r) => r.id);

      if (missingIds.length > 0) {
        const fallbackSuggestions = suggestions.filter((s) => missingIds.includes(s.id));
        if (fallbackSuggestions.length > 0) {
          const fallback = await suggestionsApi.applyDirect({
            ds_id: dsId,
            suggestions: fallbackSuggestions,
            dry_run: dryRun,
          });
          // Merge fallback results over the skipped placeholders.
          const fallbackById = new Map(fallback.results.map((r) => [r.id, r]));
          response.results = response.results.map((r) => fallbackById.get(r.id) ?? r);
        }
      }

      // Add to history
      const historyEntry: ApplyHistoryItem = {
        timestamp: new Date().toISOString(),
        ds_id: dsId,
        suggestion_ids: ids,
        dry_run: dryRun,
        results: response.results,
      };
      addToHistory(historyEntry);

      // Show results
      const successCount = response.results.filter((r) => r.status === 'success').length;
      const errorCount = response.results.filter((r) => r.status === 'error').length;

      if (errorCount > 0) {
        showToast(
          `Applied ${successCount}/${ids.length} suggestions (${errorCount} failed)`,
          'error'
        );
      } else {
        showToast(
          `✓ Successfully applied ${successCount} suggestion(s)${dryRun ? ' (dry-run)' : ''}`,
          'success'
        );
      }

      // Show rollback info
      response.results.forEach((result) => {
        if (result.rollback_sql) {
          console.log(`Rollback SQL for ${result.id}:`, result.rollback_sql);
        }
      });
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Apply failed', 'error');
    }
  };

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const copyToClipboard = (text: string) => {
    const windowsText = text.replace(/\n/g, '\r\n');
    navigator.clipboard.writeText(windowsText);
    showToast('Copied to clipboard', 'success');
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--bg-primary)',
      }}
    >
      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '12px 20px',
            backgroundColor: toast.type === 'success' ? '#10b981' : '#ef4444',
            color: 'white',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            zIndex: 1000,
            fontWeight: '500',
          }}
        >
          {toast.message}
        </div>
      )}

      {/* Toolbar */}
      <div
        style={{
          padding: '16px',
          borderBottom: '1px solid var(--border-color)',
          backgroundColor: 'var(--bg-secondary)',
        }}
      >
        <h2 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
          🔧 Query Optimizer
        </h2>

        {/* SQL Input */}
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          placeholder="Enter SQL query to analyze..."
          style={{
            width: '100%',
            minHeight: '120px',
            padding: '12px',
            fontSize: '14px',
            fontFamily: 'monospace',
            border: '1px solid var(--border-color)',
            borderRadius: '6px',
            resize: 'vertical',
            marginBottom: '12px',
          }}
        />

        {/* Controls */}
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Include AI */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px' }}>
            <input
              type="checkbox"
              checked={includeAI}
              onChange={(e) => setIncludeAI(e.target.checked)}
            />
            Include AI Suggestions
          </label>

          {/* Dry Run */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px' }}>
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
            />
            Dry Run Mode
          </label>

          {/* Top K */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px' }}>
            Top K:
            <input
              type="number"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              min={1}
              max={50}
              style={{
                width: '60px',
                padding: '4px 8px',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
              }}
            />
          </label>

          {/* Analyze Button */}
          <button
            onClick={handleAnalyze}
            disabled={loading || !sql.trim()}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              backgroundColor: loading ? '#9ca3af' : 'var(--primary)',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: '600',
            }}
          >
            {loading ? '⏳ Analyzing...' : '🔍 Analyze (Ctrl+Enter)'}
          </button>

          {/* Apply Selected */}
          {selectedIds.size > 0 && (
            <button
              onClick={handleApplySelected}
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                backgroundColor: '#10b981',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: '600',
              }}
            >
              ⚡ Apply Selected ({selectedIds.size})
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {/* Error */}
        {error && (
          <div
            style={{
              padding: '12px',
              backgroundColor: 'var(--error-bg)',
              color: 'var(--error)',
              borderRadius: '6px',
              marginBottom: '16px',
            }}
          >
            ❌ {error}
          </div>
        )}

        {/* Notes */}
        {notes.length > 0 && (
          <div
            style={{
              padding: '12px',
              backgroundColor: '#fef3c7',
              color: '#92400e',
              borderRadius: '6px',
              marginBottom: '16px',
              fontSize: '14px',
            }}
          >
            {notes.map((note, i) => (
              <div key={i}>📌 {note}</div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && suggestions.length === 0 && !error && (
          <div
            style={{
              textAlign: 'center',
              padding: '48px',
              color: 'var(--text-secondary)',
              fontSize: '15px',
            }}
          >
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔍</div>
            <div style={{ fontWeight: '600', marginBottom: '8px' }}>No Suggestions Yet</div>
            <div>Enter a SQL query and click Analyze to get optimization suggestions.</div>
          </div>
        )}

        {/* Query Suggestions */}
        {groupedSuggestions.query.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <h3
              style={{
                fontSize: '16px',
                fontWeight: '600',
                marginBottom: '12px',
                color: '#06b6d4',
              }}
            >
              🎯 Query-Level Suggestions ({groupedSuggestions.query.length})
            </h3>
            {groupedSuggestions.query.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                isSelected={selectedIds.has(suggestion.id)}
                onToggleSelect={handleToggleSelect}
                onApply={handleApplySingle}
              />
            ))}
          </div>
        )}

        {/* Table Suggestions */}
        {groupedSuggestions.table.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <h3
              style={{
                fontSize: '16px',
                fontWeight: '600',
                marginBottom: '12px',
                color: '#3b82f6',
              }}
            >
              📊 Table-Level Suggestions ({groupedSuggestions.table.length})
            </h3>
            {groupedSuggestions.table.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                isSelected={selectedIds.has(suggestion.id)}
                onToggleSelect={handleToggleSelect}
                onApply={handleApplySingle}
              />
            ))}
          </div>
        )}

        {/* DB Suggestions */}
        {groupedSuggestions.db.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <h3
              style={{
                fontSize: '16px',
                fontWeight: '600',
                marginBottom: '12px',
                color: '#8b5cf6',
              }}
            >
              🗄️ Database-Level Suggestions ({groupedSuggestions.db.length})
            </h3>
            {groupedSuggestions.db.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                isSelected={selectedIds.has(suggestion.id)}
                onToggleSelect={handleToggleSelect}
                onApply={handleApplySingle}
              />
            ))}
          </div>
        )}

        {/* History Panel */}
        {history.length > 0 && (
          <div style={{ marginTop: '32px', borderTop: '2px solid var(--border-color)', paddingTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: '600' }}>
                📜 Application History
              </h3>
              <button
                onClick={clearHistory}
                style={{
                  padding: '4px 12px',
                  fontSize: '12px',
                  backgroundColor: '#ef4444',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                Clear History
              </button>
            </div>

            {history.slice(0, 10).map((entry, idx) => (
              <div
                key={idx}
                style={{
                  padding: '12px',
                  backgroundColor: 'var(--bg-secondary)',
                  borderRadius: '6px',
                  marginBottom: '8px',
                  fontSize: '13px',
                }}
              >
                <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                  {new Date(entry.timestamp).toLocaleString()}
                  {entry.dry_run && (
                    <span style={{ marginLeft: '8px', color: '#f59e0b', fontSize: '11px' }}>
                      (DRY RUN)
                    </span>
                  )}
                </div>
                <div style={{ color: 'var(--text-secondary)' }}>
                  Applied {entry.suggestion_ids.length} suggestion(s)
                </div>
                <div style={{ marginTop: '6px', display: 'flex', gap: '12px', fontSize: '12px' }}>
                  {entry.results.map((result: ApplyResult, ridx: number) => (
                    <div key={ridx}>
                      <span
                        style={{
                          color:
                            result.status === 'success'
                              ? '#10b981'
                              : result.status === 'error'
                              ? '#ef4444'
                              : '#9ca3af',
                        }}
                      >
                        {result.status === 'success' ? '✓' : result.status === 'error' ? '✗' : '⊘'}
                      </span>{' '}
                      {result.message}
                      {result.rollback_sql && (
                        <button
                          onClick={() => copyToClipboard(result.rollback_sql!)}
                          style={{
                            marginLeft: '6px',
                            padding: '2px 6px',
                            fontSize: '10px',
                            backgroundColor: '#475569',
                            color: 'white',
                            border: 'none',
                            borderRadius: '3px',
                            cursor: 'pointer',
                          }}
                        >
                          Copy Rollback
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
