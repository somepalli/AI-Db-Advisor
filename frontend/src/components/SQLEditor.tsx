import { useState } from 'react';
import { analyzeApi } from '../api/client';
import type { AIAdviceResponse, Recommendation } from '../types';

interface Props {
  dataSourceId: string;
  onQueryExecute?: (sql: string) => void;
  onCopyToAIEditor?: (sql: string) => void;
}

export function SQLEditor({ dataSourceId, onQueryExecute, onCopyToAIEditor }: Props) {
  const [sql, setSql] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);
  const [aiSuggestions, setAiSuggestions] = useState<AIAdviceResponse | null>(null);
  const [rewriteAdvice, setRewriteAdvice] = useState<Recommendation[]>([]);
  const [indexAdvice, setIndexAdvice] = useState<Recommendation[]>([]);
  const [explainPlan, setExplainPlan] = useState<any>(null);
  const [loadingSection, setLoadingSection] = useState<string>('');

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

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px' }}>
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

      <div style={{ flex: '1', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          placeholder="-- Enter your SQL query here...
SELECT * FROM users WHERE active = true LIMIT 10;"
          style={{
            flex: '1',
            minHeight: '150px',
            padding: '12px',
            fontSize: '14px',
            fontFamily: 'monospace',
            border: '1px solid var(--border-color)',
            borderRadius: '6px',
            resize: 'vertical',
          }}
        />

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
