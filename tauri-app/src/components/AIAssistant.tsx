import { useState, useEffect, useRef } from 'react';
import { Sparkles, Send, Loader2, Copy, Code, Database, Zap, X, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { aiChatApi, chatHistoryApi, optimizationApi, type ChatMessage } from '../api/client';
import { MessageRenderer } from './MessageRenderer';
import { ChatHistoryDropdown } from './ChatHistoryDropdown';
import { useOptimization } from '../lib/optimizationContext';

interface Props {
  dataSourceId: string | null;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sql?: string;
  suggestions?: Array<{
    type: string;
    summary: string;
    sql?: string;
    rationale?: string;
  }>;
}

export function AIAssistant({ dataSourceId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => `session_${Date.now()}`);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Optimization results pushed from the schema explorer (Optimize DB / Table)
  const {
    result: optResult,
    loading: optLoading,
    setResult: setOptResult,
    requestRefresh,
  } = useOptimization();
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set());
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyResults, setApplyResults] = useState<any>(null);

  // Reset selection/results whenever a new optimization result arrives.
  useEffect(() => {
    setSelectedSuggestions(new Set());
    setApplyResults(null);
  }, [optResult]);

  const toggleSuggestion = (id: string) =>
    setSelectedSuggestions((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const handleApplySelected = async () => {
    if (!optResult) return;
    const suggestions = optResult.data.suggestions || [];
    const sqlStatements = suggestions
      .filter((s: any) => selectedSuggestions.has(s.id) && s.executable && s.sql)
      .map((s: any) => s.sql);
    if (sqlStatements.length === 0) return;
    if (
      !confirm(
        `Apply ${sqlStatements.length} optimization(s)? This will execute SQL on your database.`
      )
    ) {
      return;
    }
    try {
      setApplyLoading(true);
      const r = await optimizationApi.applyOptimizations(optResult.dsId, sqlStatements);
      setApplyResults(r);
      // Reload the matching schema explorer so applied indexes/changes show up.
      if (r.success_count > 0) {
        requestRefresh(optResult.dsId);
      }
    } catch (err) {
      setApplyResults({
        success_count: 0,
        error_count: 1,
        results: [{ status: 'error', message: (err as Error).message, sql: '' }],
      });
    } finally {
      setApplyLoading(false);
    }
  };

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    // Load chat history when dataSourceId or sessionId changes
    if (dataSourceId) {
      loadChatHistory();
    }
  }, [dataSourceId, sessionId]);

  const loadChatHistory = async () => {
    if (!dataSourceId) return;

    try {
      setHistoryLoaded(false);
      const response = await chatHistoryApi.getSession(dataSourceId, sessionId);

      // Convert history messages to Message format
      const historyMessages: Message[] = response.messages
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        .map((msg) => ({
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
        }));

      setMessages(historyMessages);
      setHistoryLoaded(true);

      console.log(`Loaded ${historyMessages.length} messages from session ${sessionId}`);
    } catch (err) {
      console.error('Failed to load chat history:', err);
      setMessages([]);
      setHistoryLoaded(true);
    }
  };

  const handleNewSession = () => {
    const newSessionId = `session_${Date.now()}`;
    setSessionId(newSessionId);
    setMessages([]);
    console.log(`Created new session: ${newSessionId}`);
  };

  const handleSessionChange = async (newSessionId: string) => {
    console.log(`Switching to session: ${newSessionId}`);
    setSessionId(newSessionId);
  };

  const handleSend = async () => {
    if (!input.trim() || !dataSourceId || loading) return;

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    // Create placeholder for streaming response
    const streamingMessageIndex = messages.length + 1;
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: '',
    }]);

    try {
      const conversationHistory: ChatMessage[] = messages.map(m => ({
        role: m.role,
        content: m.content,
      }));

      const streamGenerator = aiChatApi.chatStream({
        ds_id: dataSourceId,
        message: userMessage.content,
        conversation_history: conversationHistory,
        session_id: sessionId,
        save_to_history: true,
      });

      let accumulatedContent = '';

      for await (const chunk of streamGenerator) {
        if (chunk.type === 'token' && chunk.content) {
          // Append token to accumulated content
          accumulatedContent += chunk.content;

          // Update the streaming message in real-time
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[streamingMessageIndex] = {
              role: 'assistant',
              content: accumulatedContent,
            };
            return newMessages;
          });
        } else if (chunk.type === 'done') {
          // Streaming complete
          break;
        } else if (chunk.type === 'error') {
          throw new Error(chunk.message || 'Streaming error');
        }
      }

    } catch (error) {
      // Replace streaming message with error
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[streamingMessageIndex] = {
          role: 'assistant',
          content: `Error: ${(error as Error).message}`,
        };
        return newMessages;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-sm font-semibold">AI Assistant</h2>
          </div>
          {dataSourceId && (
            <ChatHistoryDropdown
              dataSourceId={dataSourceId}
              currentSessionId={sessionId}
              onSessionChange={handleSessionChange}
              onNewSession={handleNewSession}
            />
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Ask questions about your database
        </p>
      </div>

      {/* Optimization results (pushed from the schema explorer) */}
      {(optLoading || optResult) && (
        <div className="border-b border-border bg-primary/5 max-h-[45%] overflow-y-auto p-3">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-sm font-semibold text-primary flex items-center gap-2">
              {optResult?.type === 'table' ? (
                <Zap className="h-4 w-4" />
              ) : (
                <Database className="h-4 w-4" />
              )}
              {optResult?.type === 'table' ? 'Table Optimization' : 'Database Optimization'}
            </h3>
            {!optLoading && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setOptResult(null)}
                title="Dismiss"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>

          {optLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-3">
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating optimization suggestions...
            </div>
          ) : optResult ? (
            <>
              <div className="text-xs text-muted-foreground mb-2">
                {optResult.type === 'database'
                  ? `Tables: ${optResult.data.table_count} | Indexes: ${optResult.data.index_count}`
                  : `Table: ${optResult.data.table} | Columns: ${optResult.data.column_count} | Indexes: ${optResult.data.index_count}`}
              </div>
              <div className="space-y-2">
                {optResult.data.suggestions?.map((s: any) => {
                  const sev =
                    s.severity === 'high'
                      ? 'border-l-destructive'
                      : s.severity === 'medium'
                      ? 'border-l-warning'
                      : 'border-l-primary';
                  return (
                    <Card key={s.id} className={`border-l-4 ${sev}`}>
                      <CardContent className="p-3 flex gap-3 items-start">
                        {s.executable && (
                          <input
                            type="checkbox"
                            checked={selectedSuggestions.has(s.id)}
                            onChange={() => toggleSuggestion(s.id)}
                            className="mt-1"
                          />
                        )}
                        <div className="flex-1 space-y-2 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-semibold">
                              {s.category?.toUpperCase()}: {s.summary}
                            </span>
                            {s.severity && (
                              <Badge
                                variant={
                                  s.severity === 'high'
                                    ? 'destructive'
                                    : s.severity === 'medium'
                                    ? 'warning'
                                    : 'default'
                                }
                                className="text-xs"
                              >
                                {s.severity}
                              </Badge>
                            )}
                          </div>
                          {s.details && (
                            <div className="text-xs text-muted-foreground whitespace-pre-wrap">
                              {s.details}
                            </div>
                          )}
                          {s.sql && (
                            <pre className="text-[10px] p-2 bg-muted rounded font-mono whitespace-pre-wrap overflow-x-auto">
                              {s.sql}
                            </pre>
                          )}
                          {s.recommendation && (
                            <div className="text-xs text-primary">{s.recommendation}</div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

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

              {applyResults && (
                <Card
                  className={`mt-3 ${
                    applyResults.error_count > 0 ? 'bg-destructive/10' : 'bg-primary/10'
                  }`}
                >
                  <CardContent className="p-3">
                    <div className="text-sm font-semibold mb-2">
                      Apply Results: {applyResults.success_count} succeeded,{' '}
                      {applyResults.error_count} failed
                    </div>
                    <div className="space-y-2">
                      {applyResults.results?.map((r: any, idx: number) => (
                        <Card key={idx}>
                          <CardContent className="p-2">
                            <div
                              className={`text-xs font-semibold ${
                                r.status === 'success' ? 'text-primary' : 'text-destructive'
                              }`}
                            >
                              {r.message}
                            </div>
                            {r.sql && (
                              <div className="font-mono text-[10px] mt-1 text-muted-foreground">
                                {r.sql}
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : null}
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {!dataSourceId ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Sparkles className="h-12 w-12 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground">
              Select a connection to start<br />chatting with AI
            </p>
          </div>
        ) : !historyLoaded ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Loader2 className="h-12 w-12 text-primary mb-3 animate-spin" />
            <p className="text-sm text-muted-foreground">
              Loading chat history...
            </p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Sparkles className="h-12 w-12 text-primary mb-3" />
            <p className="text-sm font-semibold mb-2">Start a conversation</p>
            <p className="text-xs text-muted-foreground mb-4">
              Ask me anything about your database:
            </p>
            <div className="space-y-2 text-xs text-muted-foreground text-left">
              <div>• "Show me slow queries"</div>
              <div>• "Suggest indexes for users table"</div>
              <div>• "Optimize this query: SELECT..."</div>
              <div>• "Explain the execution plan"</div>
            </div>
          </div>
        ) : (
          messages.map((message, idx) => (
            <div
              key={idx}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <Card
                className={`max-w-[85%] ${
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                <CardContent className="p-3">
                  <MessageRenderer content={message.content} role={message.role} />

                  {message.sql && (
                    <div className="mt-2 pt-2 border-t border-border/50">
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant="outline" className="text-xs">
                          <Code className="h-3 w-3 mr-1" />
                          SQL
                        </Badge>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={() => copyToClipboard(message.sql!)}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                      <pre className="text-[10px] p-2 bg-background/50 rounded font-mono overflow-x-auto">
                        {message.sql}
                      </pre>
                    </div>
                  )}

                  {message.suggestions && message.suggestions.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/50 space-y-2">
                      <div className="text-xs font-semibold">Suggestions:</div>
                      {message.suggestions.map((suggestion, sIdx) => (
                        <Card key={sIdx} className="bg-background/30">
                          <CardContent className="p-2">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge variant="outline" className="text-xs">
                                {suggestion.type}
                              </Badge>
                              <span className="text-xs font-semibold">{suggestion.summary}</span>
                            </div>
                            {suggestion.rationale && (
                              <div className="text-xs text-muted-foreground mb-1">
                                {suggestion.rationale}
                              </div>
                            )}
                            {suggestion.sql && (
                              <pre className="text-[10px] p-2 bg-background/50 rounded font-mono overflow-x-auto">
                                {suggestion.sql}
                              </pre>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          ))
        )}

        {loading && (
          <div className="flex justify-start">
            <Card className="bg-muted">
              <CardContent className="p-3 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm text-muted-foreground">AI is thinking...</span>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Input */}
      {dataSourceId && (
        <div className="p-4 border-t border-border">
          <div className="flex gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about your database..."
              className="text-sm min-h-[60px] max-h-[120px] resize-none"
              disabled={loading}
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              size="icon"
              className="h-[60px] w-[60px]"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      )}
    </div>
  );
}
