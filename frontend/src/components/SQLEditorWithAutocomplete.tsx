import { useState, useEffect, useRef } from 'react';
import { analyzeApi } from '../api/client';
import type { SchemaResponse, AIAdviceResponse, Recommendation } from '../types';

interface Props {
  dataSourceId: string;
  onQueryExecute?: (sql: string) => void;
  onCopyToAIEditor?: (sql: string) => void;
}

interface AutocompleteItem {
  type: 'table' | 'column' | 'keyword';
  value: string;
  table?: string;
}

const SQL_KEYWORDS = [
  'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
  'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE',
  'ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'OFFSET',
  'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP',
  'AS', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
  'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'NULL', 'IS', 'NOT NULL',
];

export function SQLEditorWithAutocomplete({ dataSourceId, onQueryExecute, onCopyToAIEditor }: Props) {
  const [sql, setSql] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [autocompleteItems, setAutocompleteItems] = useState<AutocompleteItem[]>([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [syntaxErrors, setSyntaxErrors] = useState<Array<{ start: number; end: number; message: string }>>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autocompleteRef = useRef<HTMLDivElement>(null);
  const [aiSuggestions, setAiSuggestions] = useState<AIAdviceResponse | null>(null);
  const [rewriteAdvice, setRewriteAdvice] = useState<Recommendation[]>([]);
  const [indexAdvice, setIndexAdvice] = useState<Recommendation[]>([]);
  const [explainPlan, setExplainPlan] = useState<any>(null);
  const [loadingSection, setLoadingSection] = useState<string>('');

  useEffect(() => {
    loadSchema();
  }, [dataSourceId]);

  const loadSchema = async () => {
    try {
      const data = await analyzeApi.getSchema(dataSourceId);
      setSchema(data);
    } catch (err) {
      console.error('Failed to load schema:', err);
    }
  };

  const validateSQL = (query: string) => {
    const errors: Array<{ start: number; end: number; message: string }> = [];

    // Basic syntax validation
    const lines = query.split('\n');
    let position = 0;

    lines.forEach((line, lineIndex) => {
      // Check for common syntax errors

      // Unclosed quotes
      const singleQuotes = (line.match(/'/g) || []).length;
      const doubleQuotes = (line.match(/"/g) || []).length;

      if (singleQuotes % 2 !== 0) {
        errors.push({
          start: position,
          end: position + line.length,
          message: 'Unclosed single quote'
        });
      }

      if (doubleQuotes % 2 !== 0) {
        errors.push({
          start: position,
          end: position + line.length,
          message: 'Unclosed double quote'
        });
      }

      // Check for invalid table names (if schema is loaded)
      if (schema) {
        const tableNames = Object.keys(schema.tables);
        const fromMatch = line.match(/FROM\s+(\w+)/i);
        const joinMatch = line.match(/JOIN\s+(\w+)/i);

        if (fromMatch && fromMatch[1]) {
          const tableName = fromMatch[1];
          if (!tableNames.includes(tableName) && !tableName.match(/^\d/)) {
            const tableStart = position + line.indexOf(tableName);
            errors.push({
              start: tableStart,
              end: tableStart + tableName.length,
              message: `Unknown table: ${tableName}`
            });
          }
        }

        if (joinMatch && joinMatch[1]) {
          const tableName = joinMatch[1];
          if (!tableNames.includes(tableName) && !tableName.match(/^\d/)) {
            const tableStart = position + line.indexOf(tableName);
            errors.push({
              start: tableStart,
              end: tableStart + tableName.length,
              message: `Unknown table: ${tableName}`
            });
          }
        }
      }

      position += line.length + 1; // +1 for newline
    });

    setSyntaxErrors(errors);
  };

  const getAutocompleteItems = (query: string, cursorPos: number): AutocompleteItem[] => {
    if (!schema) return [];

    const beforeCursor = query.substring(0, cursorPos);
    const words = beforeCursor.split(/\s+/);
    const currentWord = words[words.length - 1].toLowerCase();

    const items: AutocompleteItem[] = [];

    // Add table names
    Object.keys(schema.tables).forEach(tableName => {
      if (tableName.toLowerCase().includes(currentWord)) {
        items.push({ type: 'table', value: tableName });
      }
    });

    // Add column names from all tables
    Object.entries(schema.tables).forEach(([tableName, columns]) => {
      columns.forEach(col => {
        if (col.column.toLowerCase().includes(currentWord)) {
          items.push({ type: 'column', value: col.column, table: tableName });
        }
      });
    });

    // Add SQL keywords
    SQL_KEYWORDS.forEach(keyword => {
      if (keyword.toLowerCase().includes(currentWord)) {
        items.push({ type: 'keyword', value: keyword });
      }
    });

    return items.slice(0, 10); // Limit to 10 suggestions
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    const cursorPos = e.target.selectionStart;

    setSql(newValue);
    setCursorPosition(cursorPos);

    // Validate SQL
    validateSQL(newValue);

    // Get autocomplete suggestions
    const items = getAutocompleteItems(newValue, cursorPos);
    setAutocompleteItems(items);
    setShowAutocomplete(items.length > 0 && newValue.length > 0);
    setSelectedIndex(0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!showAutocomplete) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, autocompleteItems.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && autocompleteItems.length > 0) {
      e.preventDefault();
      insertAutocomplete(autocompleteItems[selectedIndex]);
    } else if (e.key === 'Escape') {
      setShowAutocomplete(false);
    }
  };

  const insertAutocomplete = (item: AutocompleteItem) => {
    if (!textareaRef.current) return;

    const beforeCursor = sql.substring(0, cursorPosition);
    const afterCursor = sql.substring(cursorPosition);
    const words = beforeCursor.split(/\s+/);
    const currentWord = words[words.length - 1];

    const beforeWord = beforeCursor.substring(0, beforeCursor.length - currentWord.length);
    const newValue = beforeWord + item.value + afterCursor;

    setSql(newValue);
    setShowAutocomplete(false);

    // Set cursor position after inserted text
    setTimeout(() => {
      if (textareaRef.current) {
        const newCursorPos = beforeWord.length + item.value.length;
        textareaRef.current.selectionStart = newCursorPos;
        textareaRef.current.selectionEnd = newCursorPos;
        textareaRef.current.focus();
      }
    }, 0);
  };

  const handleExecute = async () => {
    if (!sql.trim()) {
      setError('Please enter a SQL query');
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);
    setAiSuggestions(null);
    setRewriteAdvice([]);
    setIndexAdvice([]);
    setExplainPlan(null);

    try {
      // Execute all analyses in sequence to show results in order

      // 1. AI Suggestions first
      setLoadingSection('AI Suggestions');
      try {
        const aiResponse = await analyzeApi.adviseAI(dataSourceId, sql);
        setAiSuggestions(aiResponse);
      } catch (err) {
        console.error('AI Suggestions failed:', err);
      }

      // 2. Rewrite Advice
      setLoadingSection('Rewrite Advice');
      try {
        const rewrite = await analyzeApi.adviseRewrite(dataSourceId, sql);
        setRewriteAdvice(rewrite);
      } catch (err) {
        console.error('Rewrite Advice failed:', err);
      }

      // 3. Index Advice
      setLoadingSection('Index Advice');
      try {
        const index = await analyzeApi.adviseIndex(dataSourceId, sql);
        setIndexAdvice(index);
      } catch (err) {
        console.error('Index Advice failed:', err);
      }

      // 4. Explain Plan
      setLoadingSection('Explain Plan');
      try {
        const plan = await analyzeApi.explain(dataSourceId, sql, false);
        setExplainPlan(plan);
      } catch (err) {
        console.error('Explain Plan failed:', err);
      }

      setResults({ success: true });

      if (onQueryExecute) {
        onQueryExecute(sql);
      }
    } catch (err) {
      setError('Query execution failed: ' + (err as Error).message);
    } finally {
      setLoading(false);
      setLoadingSection('');
    }
  };

  const handleClear = () => {
    setSql('');
    setResults(null);
    setError(null);
    setSyntaxErrors([]);
    setShowAutocomplete(false);
    setAiSuggestions(null);
    setRewriteAdvice([]);
    setIndexAdvice([]);
    setExplainPlan(null);
  };

  const handleCopyToAIEditor = () => {
    if (onCopyToAIEditor && sql.trim()) {
      onCopyToAIEditor(sql);
    }
  };

  const getHighlightedSQL = () => {
    if (syntaxErrors.length === 0) return sql;

    let result = sql;
    const parts: Array<{ text: string; error: boolean }> = [];
    let lastEnd = 0;

    syntaxErrors.forEach(error => {
      if (error.start > lastEnd) {
        parts.push({ text: sql.substring(lastEnd, error.start), error: false });
      }
      parts.push({ text: sql.substring(error.start, error.end), error: true });
      lastEnd = error.end;
    });

    if (lastEnd < sql.length) {
      parts.push({ text: sql.substring(lastEnd), error: false });
    }

    return parts;
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px', position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ fontSize: '16px', margin: 0 }}>SQL Editor</h3>
        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          Connected to: <strong>{dataSourceId}</strong>
        </div>
      </div>

      {error && (
        <div style={{
          padding: '12px',
          backgroundColor: 'var(--error-bg)',
          color: 'var(--error)',
          borderRadius: '6px',
          marginBottom: '12px',
          fontSize: '13px',
        }}>
          {error}
        </div>
      )}

      <div style={{ flex: '1', display: 'flex', flexDirection: 'column', gap: '12px', position: 'relative' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <textarea
            ref={textareaRef}
            value={sql}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="-- Enter your SQL query here...
-- Start typing to see table and column suggestions
SELECT * FROM users WHERE active = true LIMIT 10;"
            style={{
              width: '100%',
              height: '100%',
              minHeight: '150px',
              padding: '12px',
              fontSize: '14px',
              fontFamily: 'monospace',
              border: syntaxErrors.length > 0 ? '2px dotted var(--error)' : '1px solid var(--border-color)',
              borderRadius: '6px',
              resize: 'vertical',
              backgroundColor: syntaxErrors.length > 0 ? 'rgba(239, 68, 68, 0.05)' : 'white',
            }}
          />

          {showAutocomplete && autocompleteItems.length > 0 && (
            <div
              ref={autocompleteRef}
              style={{
                position: 'absolute',
                top: '100%',
                left: '12px',
                marginTop: '4px',
                backgroundColor: 'white',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                maxHeight: '200px',
                overflowY: 'auto',
                zIndex: 1000,
                minWidth: '250px',
              }}
            >
              {autocompleteItems.map((item, index) => (
                <div
                  key={index}
                  onClick={() => insertAutocomplete(item)}
                  style={{
                    padding: '8px 12px',
                    cursor: 'pointer',
                    backgroundColor: index === selectedIndex ? 'var(--bg-secondary)' : 'white',
                    fontSize: '13px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                >
                  <span style={{
                    fontSize: '10px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: item.type === 'table' ? '#3b82f6' : item.type === 'column' ? '#10b981' : '#6b7280',
                    color: 'white',
                    fontWeight: 600,
                  }}>
                    {item.type === 'table' ? 'T' : item.type === 'column' ? 'C' : 'K'}
                  </span>
                  <span style={{ fontFamily: 'monospace', flex: 1 }}>{item.value}</span>
                  {item.table && (
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {item.table}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {syntaxErrors.length > 0 && (
          <div style={{
            padding: '8px 12px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            borderLeft: '3px solid var(--error)',
            borderRadius: '4px',
            fontSize: '12px',
            color: 'var(--error)',
          }}>
            {syntaxErrors.map((err, idx) => (
              <div key={idx}>⚠ {err.message}</div>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={handleExecute}
            disabled={loading}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              backgroundColor: 'var(--primary)',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? `⏳ ${loadingSection || 'Executing'}...` : '▶ Execute'}
          </button>
          <button
            onClick={handleClear}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              backgroundColor: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            🗑️ Clear
          </button>
          {onCopyToAIEditor && (
            <button
              onClick={handleCopyToAIEditor}
              disabled={!sql.trim()}
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                cursor: sql.trim() ? 'pointer' : 'not-allowed',
                opacity: sql.trim() ? 1 : 0.6,
              }}
            >
              📋 Copy to AI SQL Editor
            </button>
          )}
        </div>

        {/* AI Suggestions Section */}
        {aiSuggestions && (
          <div style={{
            marginTop: '12px',
            padding: '12px',
            backgroundColor: 'var(--bg-secondary)',
            borderRadius: '6px',
          }}>
            <h4 style={{ fontSize: '14px', marginBottom: '8px', color: 'var(--primary)' }}>🤖 AI Suggestions</h4>
            {aiSuggestions.suggestions.length === 0 ? (
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>No AI suggestions available.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {aiSuggestions.suggestions.map((suggestion, idx) => (
                  <div key={idx} style={{
                    padding: '10px',
                    backgroundColor: 'white',
                    borderRadius: '4px',
                    border: '1px solid var(--border-color)',
                  }}>
                    <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
                      {suggestion.type}
                    </div>
                    <div style={{ fontSize: '12px', marginBottom: '6px' }}>
                      {suggestion.summary}
                    </div>
                    {suggestion.rationale && (
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                        {suggestion.rationale}
                      </div>
                    )}
                    {(suggestion.new_sql || suggestion.sql_fix) && (
                      <pre style={{
                        fontSize: '11px',
                        padding: '8px',
                        backgroundColor: '#f5f5f5',
                        borderRadius: '4px',
                        overflowX: 'auto',
                        marginTop: '6px',
                      }}>
                        {suggestion.new_sql || suggestion.sql_fix}
                      </pre>
                    )}
                    {suggestion.expected_gain && (
                      <div style={{ fontSize: '11px', color: '#10b981', marginTop: '6px' }}>
                        Expected gain: {suggestion.expected_gain}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Rewrite Advice Section */}
        {rewriteAdvice.length > 0 && (
          <div style={{
            marginTop: '12px',
            padding: '12px',
            backgroundColor: 'var(--bg-secondary)',
            borderRadius: '6px',
          }}>
            <h4 style={{ fontSize: '14px', marginBottom: '8px', color: '#f59e0b' }}>✏️ Rewrite Advice</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {rewriteAdvice.map((advice, idx) => (
                <div key={idx} style={{
                  padding: '10px',
                  backgroundColor: 'white',
                  borderRadius: '4px',
                  border: '1px solid var(--border-color)',
                }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
                    {advice.category}
                  </div>
                  <div style={{ fontSize: '12px', marginBottom: '6px' }}>
                    {advice.summary}
                  </div>
                  {advice.sql_fix && (
                    <pre style={{
                      fontSize: '11px',
                      padding: '8px',
                      backgroundColor: '#f5f5f5',
                      borderRadius: '4px',
                      overflowX: 'auto',
                      marginTop: '6px',
                    }}>
                      {advice.sql_fix}
                    </pre>
                  )}
                  {advice.expected_gain && (
                    <div style={{ fontSize: '11px', color: '#10b981', marginTop: '6px' }}>
                      Expected gain: {advice.expected_gain}
                    </div>
                  )}
                  {advice.risk && (
                    <div style={{ fontSize: '11px', color: '#ef4444', marginTop: '6px' }}>
                      Risk: {advice.risk}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Index Advice Section */}
        {indexAdvice.length > 0 && (
          <div style={{
            marginTop: '12px',
            padding: '12px',
            backgroundColor: 'var(--bg-secondary)',
            borderRadius: '6px',
          }}>
            <h4 style={{ fontSize: '14px', marginBottom: '8px', color: '#8b5cf6' }}>📊 Index Advice</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {indexAdvice.map((advice, idx) => (
                <div key={idx} style={{
                  padding: '10px',
                  backgroundColor: 'white',
                  borderRadius: '4px',
                  border: '1px solid var(--border-color)',
                }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
                    {advice.category}
                  </div>
                  <div style={{ fontSize: '12px', marginBottom: '6px' }}>
                    {advice.summary}
                  </div>
                  {advice.sql_fix && (
                    <pre style={{
                      fontSize: '11px',
                      padding: '8px',
                      backgroundColor: '#f5f5f5',
                      borderRadius: '4px',
                      overflowX: 'auto',
                      marginTop: '6px',
                    }}>
                      {advice.sql_fix}
                    </pre>
                  )}
                  {advice.expected_gain && (
                    <div style={{ fontSize: '11px', color: '#10b981', marginTop: '6px' }}>
                      Expected gain: {advice.expected_gain}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Explain Plan Section */}
        {explainPlan && (
          <div style={{
            marginTop: '12px',
            padding: '12px',
            backgroundColor: 'var(--bg-secondary)',
            borderRadius: '6px',
          }}>
            <h4 style={{ fontSize: '14px', marginBottom: '8px', color: '#06b6d4' }}>📈 Explain Plan</h4>
            <pre style={{
              fontSize: '12px',
              margin: 0,
              whiteSpace: 'pre-wrap',
              wordWrap: 'break-word',
              padding: '10px',
              backgroundColor: 'white',
              borderRadius: '4px',
              border: '1px solid var(--border-color)',
            }}>
              {JSON.stringify(explainPlan, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
