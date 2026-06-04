import { useState } from 'react';
import { analyzeApi } from '../api/client';
import type { AIAdviceResponse, Recommendation } from '../types';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Textarea } from './ui/textarea';
import { Play, Trash2, Copy } from 'lucide-react';

interface Props {
  dataSourceId: string;
  onQueryExecute?: (sql: string) => void;
  onCopyToAIEditor?: (sql: string) => void;
}

export function SQLEditor({ dataSourceId, onQueryExecute, onCopyToAIEditor }: Props) {
  const [sql, setSql] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, setResults] = useState<any>(null);
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
    <div className="h-full flex flex-col p-4">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm font-semibold">SQL Editor</h3>
        <div className="text-xs text-muted-foreground">
          Connected to: <strong>{dataSourceId}</strong>
        </div>
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive text-xs p-3 rounded-md mb-3">
          {error}
        </div>
      )}

      <div className="flex-1 flex flex-col gap-3">
        <Textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          placeholder="-- Enter your SQL query here...&#10;SELECT * FROM users WHERE active = true LIMIT 10;"
          className="flex-1 min-h-[150px] text-sm font-mono resize-y"
        />

        <div className="flex gap-2">
          <Button
            onClick={handleExecute}
            disabled={loading}
            size="sm"
            className="text-xs"
          >
            {loading ? (
              `${loadingSection || 'Executing'}...`
            ) : (
              <>
                <Play className="h-3 w-3" />
                Execute
              </>
            )}
          </Button>
          <Button
            onClick={handleClear}
            variant="outline"
            size="sm"
            className="text-xs"
          >
            <Trash2 className="h-3 w-3" />
            Clear
          </Button>
          {onCopyToAIEditor && (
            <Button
              onClick={handleCopyToAIEditor}
              disabled={!sql.trim()}
              variant="outline"
              size="sm"
              className="text-xs"
            >
              <Copy className="h-3 w-3" />
              Copy to AI Editor
            </Button>
          )}
        </div>

        {/* AI Suggestions Section */}
        {aiSuggestions && (
          <Card>
            <CardHeader className="p-3">
              <CardTitle className="text-sm text-primary">AI Suggestions</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              {aiSuggestions.suggestions.length === 0 ? (
                <p className="text-xs text-muted-foreground">No AI suggestions available.</p>
              ) : (
                <div className="space-y-2">
                  {aiSuggestions.suggestions.map((suggestion, idx) => (
                    <Card key={idx}>
                      <CardContent className="p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="outline" className="text-xs">
                            {suggestion.type}
                          </Badge>
                          <span className="text-xs font-semibold flex-1">{suggestion.summary}</span>
                        </div>
                        {suggestion.rationale && (
                          <div className="text-xs text-muted-foreground mb-2">
                            {suggestion.rationale}
                          </div>
                        )}
                        {(suggestion.new_sql || suggestion.sql_fix) && (
                          <pre className="text-[10px] p-2 bg-muted rounded font-mono overflow-x-auto mt-2">
                            {suggestion.new_sql || suggestion.sql_fix}
                          </pre>
                        )}
                        {suggestion.expected_gain && (
                          <div className="text-xs text-primary mt-2">
                            Expected gain: {suggestion.expected_gain}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Rewrite Advice Section */}
        {rewriteAdvice.length > 0 && (
          <Card className="border-l-4 border-l-warning">
            <CardHeader className="p-3">
              <CardTitle className="text-sm text-warning">Rewrite Advice</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <div className="space-y-2">
                {rewriteAdvice.map((advice, idx) => (
                  <Card key={idx}>
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="outline" className="text-xs">
                          {advice.category}
                        </Badge>
                        <span className="text-xs font-semibold flex-1">{advice.summary}</span>
                      </div>
                      {advice.sql_fix && (
                        <pre className="text-[10px] p-2 bg-muted rounded font-mono overflow-x-auto mt-2">
                          {advice.sql_fix}
                        </pre>
                      )}
                      {advice.expected_gain && (
                        <div className="text-xs text-primary mt-2">
                          Expected gain: {advice.expected_gain}
                        </div>
                      )}
                      {advice.risk && (
                        <Badge variant="destructive" className="mt-2 text-xs">
                          Risk: {advice.risk}
                        </Badge>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Index Advice Section */}
        {indexAdvice.length > 0 && (
          <Card className="border-l-4 border-l-primary">
            <CardHeader className="p-3">
              <CardTitle className="text-sm text-primary">Index Advice</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <div className="space-y-2">
                {indexAdvice.map((advice, idx) => (
                  <Card key={idx}>
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="outline" className="text-xs">
                          {advice.category}
                        </Badge>
                        <span className="text-xs font-semibold flex-1">{advice.summary}</span>
                      </div>
                      {advice.sql_fix && (
                        <pre className="text-[10px] p-2 bg-muted rounded font-mono overflow-x-auto mt-2">
                          {advice.sql_fix}
                        </pre>
                      )}
                      {advice.expected_gain && (
                        <div className="text-xs text-primary mt-2">
                          Expected gain: {advice.expected_gain}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Explain Plan Section */}
        {explainPlan && (
          <Card className="border-l-4 border-l-secondary">
            <CardHeader className="p-3">
              <CardTitle className="text-sm">Explain Plan</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <pre className="text-xs whitespace-pre-wrap break-words p-3 bg-muted rounded font-mono">
                {JSON.stringify(explainPlan, null, 2)}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
