import { useState, useEffect, useRef } from 'react';
import { analyzeApi, aiChatApi } from '../api/client';
import type { SchemaResponse } from '../types';
import { QueryResults } from './QueryResults';
import { MessageRenderer } from './MessageRenderer';

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
  const [, setResults] = useState<any>(null);
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [autocompleteItems, setAutocompleteItems] = useState<AutocompleteItem[]>([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [syntaxErrors, setSyntaxErrors] = useState<Array<{ start: number; end: number; message: string }>>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autocompleteRef = useRef<HTMLDivElement>(null);
  const [queryResults, setQueryResults] = useState<{
    columns: string[];
    rows: Record<string, any>[];
  } | null>(null);
  const [queryExecuting, setQueryExecuting] = useState(false);
  const [showAISuggestions, setShowAISuggestions] = useState(false);
  const [aiSuggestionsContent, setAiSuggestionsContent] = useState<string>('');
  const [aiLoading, setAiLoading] = useState(false);

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

    lines.forEach((line) => {
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

      // Check for invalid table names (if schema is loaded). Schema keys are
      // schema-qualified (e.g. "public.orders"), but users type the bare name
      // (e.g. "orders"), so compare against the unqualified form on both sides.
      if (schema) {
        const tableNames = new Set(
          Object.keys(schema.tables).map((t) => t.split('.').pop()!.toLowerCase())
        );
        const fromMatch = line.match(/FROM\s+(\w+)/i);
        const joinMatch = line.match(/JOIN\s+(\w+)/i);

        if (fromMatch && fromMatch[1]) {
          const tableName = fromMatch[1];
          if (!tableNames.has(tableName.toLowerCase()) && !tableName.match(/^\d/)) {
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
          if (!tableNames.has(tableName.toLowerCase()) && !tableName.match(/^\d/)) {
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
    setQueryResults(null);
    setQueryExecuting(true);

    try {
      // Execute query and get results (supports SELECT, DDL, DML)
      const results = await analyzeApi.executeQuery(dataSourceId, sql);

      // Check if the response contains an error
      if (results.status === 'error' && results.error) {
        setError(`${results.error.type}: ${results.error.message}`);
        setQueryResults(null);
      } else {
        setQueryResults(results);
        if (onQueryExecute) {
          onQueryExecute(sql);
        }
      }
      setQueryExecuting(false);
    } catch (err) {
      setError('Query execution failed: ' + (err as Error).message);
      setQueryExecuting(false);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setSql('');
    setResults(null);
    setError(null);
    setSyntaxErrors([]);
    setShowAutocomplete(false);
    setQueryResults(null);
    setQueryExecuting(false);
    setShowAISuggestions(false);
    setAiSuggestionsContent('');
  };

  const handleAskAI = async () => {
    if (!sql.trim()) {
      setError('Please enter a SQL query to get AI suggestions');
      return;
    }

    setShowAISuggestions(true);
    setAiLoading(true);
    setAiSuggestionsContent('');

    try {
      const streamGenerator = aiChatApi.chatStream({
        ds_id: dataSourceId,
        message: `Analyze this SQL query and provide optimization suggestions:\n\n${sql}`,
        conversation_history: [],
        session_id: `sql_editor_${Date.now()}`,
        save_to_history: false,
      });

      let accumulatedContent = '';

      for await (const chunk of streamGenerator) {
        if (chunk.type === 'token' && chunk.content) {
          accumulatedContent += chunk.content;
          setAiSuggestionsContent(accumulatedContent);
        } else if (chunk.type === 'done') {
          break;
        } else if (chunk.type === 'error') {
          throw new Error(chunk.message || 'Streaming error');
        }
      }
    } catch (err) {
      setAiSuggestionsContent(`Error: ${(err as Error).message}`);
    } finally {
      setAiLoading(false);
    }
  };

  const handleCopyToAIEditor = () => {
    if (onCopyToAIEditor && sql.trim()) {
      onCopyToAIEditor(sql);
    }
  };

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px',
      position: 'relative',
      backgroundColor: '#1e1e1e',
      color: '#e0e0e0'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ fontSize: '16px', margin: 0, color: '#ffffff' }}>SQL Editor</h3>
        <div style={{ fontSize: '12px', color: '#a0a0a0' }}>
          Connected to: <strong style={{ color: '#4fc3f7' }}>{dataSourceId}</strong>
        </div>
      </div>

      {error && (
        <div style={{
          padding: '12px',
          backgroundColor: '#3a1f1f',
          color: '#ff6b6b',
          borderRadius: '6px',
          marginBottom: '12px',
          fontSize: '13px',
          border: '1px solid #5a2f2f'
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
              border: syntaxErrors.length > 0 ? '2px dotted #ff6b6b' : '1px solid #3a3a3a',
              borderRadius: '6px',
              resize: 'vertical',
              backgroundColor: syntaxErrors.length > 0 ? '#3a1f1f' : '#2d2d2d',
              color: '#e0e0e0'
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
                backgroundColor: '#2d2d2d',
                border: '1px solid #3a3a3a',
                borderRadius: '6px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
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
                    backgroundColor: index === selectedIndex ? '#3a3a3a' : '#2d2d2d',
                    fontSize: '13px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    color: '#e0e0e0'
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
            backgroundColor: '#3a1f1f',
            borderLeft: '3px solid #ff6b6b',
            borderRadius: '4px',
            fontSize: '12px',
            color: '#ff6b6b',
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
            {loading ? '⏳ Executing...' : '▶ Execute'}
          </button>
          <button
            onClick={handleAskAI}
            disabled={aiLoading || !sql.trim()}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              backgroundColor: '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: (aiLoading || !sql.trim()) ? 'not-allowed' : 'pointer',
              opacity: (aiLoading || !sql.trim()) ? 0.6 : 1,
            }}
          >
            {aiLoading ? '⏳ AI Thinking...' : '🤖 Ask AI'}
          </button>
          <button
            onClick={handleClear}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              backgroundColor: '#3a3a3a',
              color: '#e0e0e0',
              border: '1px solid #4a4a4a',
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
                backgroundColor: '#3a3a3a',
                color: '#e0e0e0',
                border: '1px solid #4a4a4a',
                borderRadius: '6px',
                cursor: sql.trim() ? 'pointer' : 'not-allowed',
                opacity: sql.trim() ? 1 : 0.6,
              }}
            >
              📋 Copy to AI SQL Editor
            </button>
          )}
        </div>

        {/* Query Results Section */}
        {(queryResults || queryExecuting) && (
          <div style={{
            marginTop: '12px',
            padding: '12px',
            backgroundColor: '#2d2d2d',
            borderRadius: '6px',
            border: '1px solid #3a3a3a'
          }}>
            <h4 style={{ fontSize: '14px', marginBottom: '8px', color: '#4fc3f7' }}>📊 Query Results</h4>
            {queryResults ? (
              <QueryResults
                columns={queryResults.columns}
                rows={queryResults.rows}
                loading={queryExecuting}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: '40px', color: '#a0a0a0' }}>
                <p>Execute a query to see results</p>
              </div>
            )}
          </div>
        )}

        {/* AI Suggestions Section - Streaming with Code Blocks */}
        {showAISuggestions && (
          <div style={{
            marginTop: '12px',
            padding: '16px',
            backgroundColor: '#2d2d2d',
            borderRadius: '8px',
            border: '1px solid #3a3a3a',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.5)',
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '12px',
              paddingBottom: '12px',
              borderBottom: '1px solid #3a3a3a',
            }}>
              <h4 style={{ fontSize: '16px', margin: 0, color: '#4fc3f7', fontWeight: 600 }}>
                🤖 AI Suggestions {aiLoading && '(Streaming...)'}
              </h4>
              <button
                onClick={() => setShowAISuggestions(false)}
                style={{
                  padding: '4px 12px',
                  fontSize: '12px',
                  backgroundColor: 'transparent',
                  color: '#a0a0a0',
                  border: '1px solid #4a4a4a',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                ✕ Close
              </button>
            </div>

            {aiSuggestionsContent ? (
              <div style={{
                fontSize: '14px',
                lineHeight: '1.6',
                color: '#e0e0e0'
              }}>
                <MessageRenderer content={aiSuggestionsContent} role="assistant" />
              </div>
            ) : (
              <div style={{
                textAlign: 'center',
                padding: '40px',
                color: '#a0a0a0'
              }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>🤖</div>
                <p>Waiting for AI response...</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
