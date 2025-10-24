import { useState, useEffect, useRef } from 'react';
import { analyzeApi } from '../api/client';
import type { Recommendation, AIAdviceResponse, SchemaResponse } from '../types';

interface Props {
  dataSourceId: string;
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

export function QueryAnalyzer({ dataSourceId }: Props) {
  const [sql, setSql] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [explainPlan, setExplainPlan] = useState<any>(null);
  const [indexRecommendations, setIndexRecommendations] = useState<Recommendation[]>([]);
  const [rewriteRecommendations, setRewriteRecommendations] = useState<Recommendation[]>([]);
  const [aiAdvice, setAiAdvice] = useState<AIAdviceResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'explain' | 'index' | 'rewrite' | 'ai'>('explain');
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [autocompleteItems, setAutocompleteItems] = useState<AutocompleteItem[]>([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [syntaxErrors, setSyntaxErrors] = useState<Array<{ start: number; end: number; message: string }>>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    const lines = query.split('\n');
    let position = 0;

    lines.forEach((line) => {
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

      position += line.length + 1;
    });

    setSyntaxErrors(errors);
  };

  const getAutocompleteItems = (query: string, cursorPos: number): AutocompleteItem[] => {
    if (!schema) return [];

    const beforeCursor = query.substring(0, cursorPos);
    const words = beforeCursor.split(/\s+/);
    const currentWord = words[words.length - 1].toLowerCase();

    const items: AutocompleteItem[] = [];

    Object.keys(schema.tables).forEach(tableName => {
      if (tableName.toLowerCase().includes(currentWord)) {
        items.push({ type: 'table', value: tableName });
      }
    });

    Object.entries(schema.tables).forEach(([tableName, columns]) => {
      columns.forEach(col => {
        if (col.column.toLowerCase().includes(currentWord)) {
          items.push({ type: 'column', value: col.column, table: tableName });
        }
      });
    });

    SQL_KEYWORDS.forEach(keyword => {
      if (keyword.toLowerCase().includes(currentWord)) {
        items.push({ type: 'keyword', value: keyword });
      }
    });

    return items.slice(0, 10);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    const cursorPos = e.target.selectionStart;

    setSql(newValue);
    setCursorPosition(cursorPos);
    validateSQL(newValue);

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

    setTimeout(() => {
      if (textareaRef.current) {
        const newCursorPos = beforeWord.length + item.value.length;
        textareaRef.current.selectionStart = newCursorPos;
        textareaRef.current.selectionEnd = newCursorPos;
        textareaRef.current.focus();
      }
    }, 0);
  };

  const handleAnalyze = async () => {
    if (!sql.trim()) {
      setError('Please enter a SQL query');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Get EXPLAIN plan
      const plan = await analyzeApi.explain(dataSourceId, sql, false);
      setExplainPlan(plan);

      // Get recommendations
      const [indexRecs, rewriteRecs] = await Promise.all([
        analyzeApi.adviseIndex(dataSourceId, sql),
        analyzeApi.adviseRewrite(dataSourceId, sql),
      ]);

      setIndexRecommendations(indexRecs);
      setRewriteRecommendations(rewriteRecs);
    } catch (err) {
      setError('Analysis failed: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleAIAnalyze = async () => {
    if (!sql.trim()) {
      setError('Please enter a SQL query');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const advice = await analyzeApi.adviseAI(dataSourceId, sql);
      setAiAdvice(advice);
      setActiveTab('ai');
    } catch (err) {
      setError('AI analysis failed: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h2>Query Analyzer</h2>
        <p>Analyze SQL queries and get optimization recommendations for {dataSourceId}</p>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="card">
        <h3>SQL Query</h3>
        <div className="form-group" style={{ position: 'relative' }}>
          <textarea
            ref={textareaRef}
            value={sql}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Enter your SQL query here...
Start typing to see table and column suggestions"
            rows={10}
            style={{
              border: syntaxErrors.length > 0 ? '2px dotted var(--error)' : '1px solid var(--border-color)',
              backgroundColor: syntaxErrors.length > 0 ? 'rgba(239, 68, 68, 0.05)' : 'white',
            }}
          />

          {showAutocomplete && autocompleteItems.length > 0 && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% - 40px)',
                left: '12px',
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
            marginBottom: '12px',
          }}>
            {syntaxErrors.map((err, idx) => (
              <div key={idx}>⚠ {err.message}</div>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            className="btn btn-primary"
            onClick={handleAnalyze}
            disabled={loading}
          >
            {loading ? 'Analyzing...' : 'Analyze Query'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleAIAnalyze}
            disabled={loading}
          >
            🤖 AI Analysis
          </button>
        </div>
      </div>

      {(explainPlan || indexRecommendations.length > 0 || rewriteRecommendations.length > 0 || aiAdvice) && (
        <>
          <div className="card">
            <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', borderBottom: '1px solid var(--border-color)' }}>
              <button
                className={`btn ${activeTab === 'explain' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveTab('explain')}
              >
                EXPLAIN Plan
              </button>
              <button
                className={`btn ${activeTab === 'index' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveTab('index')}
              >
                Index Advice ({indexRecommendations.length})
              </button>
              <button
                className={`btn ${activeTab === 'rewrite' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveTab('rewrite')}
              >
                Rewrite Advice ({rewriteRecommendations.length})
              </button>
              {aiAdvice && (
                <button
                  className={`btn ${activeTab === 'ai' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveTab('ai')}
                >
                  AI Suggestions ({aiAdvice.suggestions?.length || 0})
                </button>
              )}
            </div>

            {activeTab === 'explain' && explainPlan && (
              <div>
                <h3>Execution Plan</h3>
                <div className="code-block">
                  <pre>{JSON.stringify(explainPlan.plan, null, 2)}</pre>
                </div>
              </div>
            )}

            {activeTab === 'index' && (
              <div>
                <h3>Index Recommendations</h3>
                {indexRecommendations.length === 0 ? (
                  <p style={{ color: 'var(--text-secondary)' }}>No index recommendations found. Your query looks good!</p>
                ) : (
                  indexRecommendations.map((rec, idx) => (
                    <div key={idx} className={`recommendation-card risk-${rec.risk || 'medium'}`}>
                      <h4>{rec.summary}</h4>
                      <div className="meta">
                        <span><strong>Category:</strong> {rec.category}</span>
                        {rec.risk && <span className={`badge ${rec.risk === 'low' ? 'success' : rec.risk === 'high' ? 'danger' : 'warning'}`}>{rec.risk.toUpperCase()} RISK</span>}
                      </div>
                      {rec.expected_gain && <p><strong>Expected Gain:</strong> {rec.expected_gain}</p>}
                      {rec.sql_fix && (
                        <>
                          <p style={{ marginTop: '12px', marginBottom: '8px' }}><strong>Suggested SQL:</strong></p>
                          <div className="code-block">
                            <pre>{rec.sql_fix}</pre>
                          </div>
                        </>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'rewrite' && (
              <div>
                <h3>Query Rewrite Recommendations</h3>
                {rewriteRecommendations.length === 0 ? (
                  <p style={{ color: 'var(--text-secondary)' }}>No rewrite suggestions found. Your query structure looks good!</p>
                ) : (
                  rewriteRecommendations.map((rec, idx) => (
                    <div key={idx} className={`recommendation-card risk-${rec.risk || 'low'}`}>
                      <h4>{rec.summary}</h4>
                      <div className="meta">
                        <span><strong>Category:</strong> {rec.category}</span>
                        {rec.risk && <span className={`badge ${rec.risk === 'low' ? 'success' : rec.risk === 'high' ? 'danger' : 'warning'}`}>{rec.risk.toUpperCase()} RISK</span>}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'ai' && aiAdvice && (
              <div>
                <h3>AI-Powered Recommendations</h3>
                {aiAdvice.suggestions?.length === 0 ? (
                  <p style={{ color: 'var(--text-secondary)' }}>No AI suggestions available.</p>
                ) : (
                  aiAdvice.suggestions?.map((sug, idx) => (
                    <div key={idx} className="recommendation-card">
                      <h4>{sug.summary}</h4>
                      <div className="meta">
                        <span><strong>Type:</strong> {sug.type}</span>
                        {sug.validated !== undefined && (
                          <span className={`badge ${sug.validated ? 'success' : 'warning'}`}>
                            {sug.validated ? '✓ Validated' : '⚠ Not Validated'}
                          </span>
                        )}
                        {sug.risk && <span className={`badge ${sug.risk === 'low' ? 'success' : sug.risk === 'high' ? 'danger' : 'warning'}`}>{sug.risk.toUpperCase()} RISK</span>}
                      </div>
                      {sug.rationale && <p style={{ marginTop: '12px' }}><strong>Rationale:</strong> {sug.rationale}</p>}
                      {sug.expected_gain && <p><strong>Expected Gain:</strong> {sug.expected_gain}</p>}
                      {(sug.new_sql || sug.sql_fix) && (
                        <>
                          <p style={{ marginTop: '12px', marginBottom: '8px' }}><strong>Suggested SQL:</strong></p>
                          <div className="code-block">
                            <pre>{sug.new_sql || sug.sql_fix}</pre>
                          </div>
                        </>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
