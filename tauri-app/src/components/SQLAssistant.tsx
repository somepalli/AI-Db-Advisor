/**
 * SQL Assistant - Enhanced SQL Editor with AI Chat Integration
 *
 * Features:
 * - Conversational AI query generation
 * - Real-time query validation
 * - Missing table detection and auto-creation
 * - Integrated suggestions panel
 * - Context-aware intelligence
 */
import { useState, useEffect, useRef } from 'react';
import { analyzeApi, aiChatApi, chatHistoryApi, type HistoryMessage, suggestionsApi, mcpApi, type MCPSuggestion } from '../api/client';
import type { SchemaResponse } from '../types';
import type { Suggestion } from '../types/suggestions';
import { ChatHistoryDropdown } from './ChatHistoryDropdown';
import { MessageRenderer } from './MessageRenderer';

interface Props {
  dataSourceId: string;
}

// Generate a unique session ID
function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

export function SQLAssistant({ dataSourceId }: Props) {
  // SQL Editor State
  const [sql, setSql] = useState('');
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [validationIssues, setValidationIssues] = useState<any[]>([]);

  // AI Chat State
  const [chatHistory, setChatHistory] = useState<any[]>([]); // Changed to any[] to support MCP cards
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>(generateSessionId()); // Persistent session ID
  const [historyLoaded, setHistoryLoaded] = useState(false);

  // Semantic Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);

  // Suggestions State
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  // MCP State (integrated with AI chat)
  const [executingMcp, setExecutingMcp] = useState<string | null>(null);

  // UI State
  const [activeTab, setActiveTab] = useState<'chat' | 'suggestions' | 'validation'>('chat');
  const [error, setError] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const sqlTextareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadSchema();
    loadChatHistory();
  }, [dataSourceId, sessionId]); // Reload when session changes

  useEffect(() => {
    // Auto-scroll chat to bottom
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  useEffect(() => {
    // Auto-validate SQL as user types (debounced)
    const timer = setTimeout(() => {
      if (sql.trim()) {
        validateSQL();
      } else {
        setValidationIssues([]);
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [sql]);

  const loadSchema = async () => {
    try {
      const data = await analyzeApi.getSchema(dataSourceId);
      setSchema(data);
    } catch (err) {
      console.error('Failed to load schema:', err);
    }
  };

  const loadChatHistory = async () => {
    try {
      setHistoryLoaded(false);
      const response = await chatHistoryApi.getSession(dataSourceId, sessionId);

      // Convert HistoryMessage[] to ChatMessage[] and sort chronologically
      const messages: any[] = response.messages
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        .map((msg: HistoryMessage) => ({
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp, // Preserve timestamp for display
        }));

      setChatHistory(messages);
      setHistoryLoaded(true);

      console.log(`Loaded ${messages.length} messages from chat history for session ${sessionId}`);

      // Auto-scroll to bottom after loading history
      setTimeout(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } catch (err) {
      console.error('Failed to load chat history:', err);
      setChatHistory([]); // Clear chat on error
      setHistoryLoaded(true); // Mark as loaded even on error to avoid infinite retry
    }
  };

  const validateSQL = async () => {
    if (!sql.trim()) return;

    try {
      const validation = await aiChatApi.validateQuery({
        ds_id: dataSourceId,
        sql: sql,
      });

      setValidationIssues(validation.issues);

      // Auto-switch to validation tab if there are critical issues
      const hasCriticalIssues = validation.issues.some(
        i => i.type === 'syntax' || i.type === 'missing_table'
      );
      if (hasCriticalIssues && activeTab === 'chat') {
        setActiveTab('validation');
      }
    } catch (err) {
      console.error('Validation failed:', err);
    }
  };

  const sendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const userMessage: any = {
      role: 'user',
      content: chatInput,
      timestamp: new Date().toISOString(),
    };

    const userInput = chatInput; // Save input before clearing
    setChatHistory(prev => [...prev, userMessage]);
    setChatInput('');
    setChatLoading(true);
    setError(null);

    // Create placeholder for streaming response
    const streamingMessageIndex = chatHistory.length + 1;
    setChatHistory(prev => [...prev, {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    }]);

    try {
      // Filter out MCP cards from conversation history (backend doesn't need them)
      const conversationHistory = chatHistory
        .filter(msg => msg.type !== 'mcp_card')
        .map(msg => ({
          role: msg.role,
          content: msg.content
        }));

      const streamGenerator = aiChatApi.chatStream({
        ds_id: dataSourceId,
        message: userInput,
        conversation_history: conversationHistory,
        current_sql: sql || undefined,
        session_id: sessionId,
        save_to_history: true,
      });

      let accumulatedContent = '';

      for await (const chunk of streamGenerator) {
        if (chunk.type === 'token' && chunk.content) {
          // Append token to accumulated content
          accumulatedContent += chunk.content;

          // Update the streaming message in real-time
          setChatHistory(prev => {
            const newMessages = [...prev];
            if (newMessages[streamingMessageIndex]) {
              newMessages[streamingMessageIndex] = {
                ...newMessages[streamingMessageIndex],
                content: accumulatedContent,
              };
            }
            return newMessages;
          });
        } else if (chunk.type === 'done') {
          // Streaming complete
          break;
        } else if (chunk.type === 'error') {
          throw new Error(chunk.message || 'Streaming error');
        }
      }

      // Note: The current streaming endpoint doesn't return SQL or suggestions
      // These features would need to be added to the backend streaming endpoint
      // For now, streaming only provides the conversational response text

    } catch (err: any) {
      // Replace streaming message with error
      setChatHistory(prev => {
        const newMessages = [...prev];
        if (newMessages[streamingMessageIndex]) {
          newMessages[streamingMessageIndex] = {
            role: 'assistant',
            content: `Error: ${err.message}`,
            timestamp: new Date().toISOString(),
          };
        }
        return newMessages;
      });
      setError(`Chat error: ${err.message}`);
      console.error('Chat error:', err);
    } finally {
      setChatLoading(false);
    }
  };

  const analyzeSQLSuggestions = async () => {
    if (!sql.trim()) {
      setError('Please enter a SQL query first');
      return;
    }

    setSuggestionsLoading(true);
    setError(null);

    try {
      const result = await suggestionsApi.analyze({
        ds_id: dataSourceId,
        sql: sql,
        include_ai: true,
        top_k: 12,
      });

      setSuggestions(result.suggestions);
      setActiveTab('suggestions');
    } catch (err: any) {
      setError(`Analysis failed: ${err.message}`);
      console.error('Analysis error:', err);
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const applySuggestion = (suggestion: Suggestion) => {
    if (suggestion.sql_fix) {
      // If it's a CREATE TABLE, append to SQL
      if (suggestion.sql_fix.toUpperCase().includes('CREATE TABLE')) {
        setSql(prev => prev ? `${prev}\n\n${suggestion.sql_fix}` : suggestion.sql_fix!);
      } else if (suggestion.category === 'index') {
        // Append index creation
        setSql(prev => prev ? `${prev}\n\n${suggestion.sql_fix}` : suggestion.sql_fix!);
      } else if (suggestion.category === 'rewrite') {
        // Replace SQL with rewrite
        setSql(suggestion.sql_fix);
      } else {
        // Append by default
        setSql(prev => prev ? `${prev}\n\n${suggestion.sql_fix}` : suggestion.sql_fix!);
      }

      // Show notification
      setError(`✓ Applied: ${suggestion.title}`);
      setTimeout(() => setError(null), 3000);
    }
  };

  const executeSQL = async () => {
    if (!sql.trim()) return;

    // First validate
    await validateSQL();

    // If there are critical issues, warn user
    const hasCriticalIssues = validationIssues.some(
      i => i.type === 'syntax' || i.type === 'missing_table'
    );

    if (hasCriticalIssues) {
      setError('⚠ Query has validation errors. Check the Validation tab.');
      setActiveTab('validation');
      return;
    }

    // Auto-analyze for suggestions
    await analyzeSQLSuggestions();
  };

  const clearAll = () => {
    setSql('');
    setSuggestions([]);
    setValidationIssues([]);
    setError(null);
  };

  const searchChatHistory = async () => {
    if (!searchQuery.trim() || searchLoading) return;

    setSearchLoading(true);
    setShowSearchResults(true);
    setError(null);

    try {
      const response = await chatHistoryApi.searchMessages({
        ds_id: dataSourceId,
        query: searchQuery,
        limit: 10,
        session_id: undefined, // Search across all sessions
      });

      setSearchResults(response.results);
      console.log(`Found ${response.results.length} messages matching "${searchQuery}"`);
    } catch (err: any) {
      setError(`Search failed: ${err.message}`);
      console.error('Search error:', err);
    } finally {
      setSearchLoading(false);
    }
  };

  const clearSearch = () => {
    setSearchQuery('');
    setSearchResults([]);
    setShowSearchResults(false);
  };


  const approveMcpSuggestion = async (suggestion: MCPSuggestion) => {
    if (!suggestion.approval_id) return;

    try {
      await mcpApi.approve(dataSourceId, suggestion.approval_id, {}, 'user');

      // Update suggestion status in chat history
      setChatHistory(prev =>
        prev.map(msg =>
          msg.type === 'mcp_card' && msg.suggestion?.id === suggestion.id
            ? { ...msg, suggestion: { ...msg.suggestion, status: 'approved' as const } }
            : msg
        )
      );

      setError(`✓ Approved: ${suggestion.description}`);
      setTimeout(() => setError(null), 3000);
    } catch (err: any) {
      setError(`Approval failed: ${err.message}`);
    }
  };

  const executeMcpSuggestion = async (suggestion: MCPSuggestion) => {
    if (!suggestion.approval_id || suggestion.status !== 'approved') return;

    setExecutingMcp(suggestion.id);
    setError(null);

    try {
      const result = await mcpApi.execute(dataSourceId, suggestion.approval_id, 'user');

      // Update suggestion status in chat history
      setChatHistory(prev =>
        prev.map(msg =>
          msg.type === 'mcp_card' && msg.suggestion?.id === suggestion.id
            ? { ...msg, suggestion: { ...msg.suggestion, status: 'executed' as const } }
            : msg
        )
      );

      // Add success message to chat
      const assistantMessage: any = {
        role: 'assistant',
        content: `✅ Successfully executed: ${suggestion.description}\n\n${result.result?.note || 'Optimization applied successfully.'}`,
        timestamp: new Date().toISOString(),
      };
      setChatHistory(prev => [...prev, assistantMessage]);

      setError(`✓ Executed successfully!`);
      setTimeout(() => setError(null), 3000);
    } catch (err: any) {
      setError(`Execution failed: ${err.message}`);

      // Update suggestion status to failed in chat history
      setChatHistory(prev =>
        prev.map(msg =>
          msg.type === 'mcp_card' && msg.suggestion?.id === suggestion.id
            ? { ...msg, suggestion: { ...msg.suggestion, status: 'failed' as const } }
            : msg
        )
      );
    } finally {
      setExecutingMcp(null);
    }
  };

  const rejectMcpSuggestion = async (suggestion: MCPSuggestion) => {
    if (!suggestion.approval_id) return;

    try {
      await mcpApi.reject(dataSourceId, suggestion.approval_id, { reason: 'User rejected' }, 'user');

      // Update status in chat history
      setChatHistory(prev =>
        prev.map(msg =>
          msg.type === 'mcp_card' && msg.suggestion?.id === suggestion.id
            ? { ...msg, suggestion: { ...msg.suggestion, status: 'rejected' as const } }
            : msg
        )
      );

      setError(`Rejected: ${suggestion.description}`);
      setTimeout(() => setError(null), 3000);
    } catch (err: any) {
      setError(`Rejection failed: ${err.message}`);
    }
  };

  const handleNewSession = () => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    setChatHistory([]);
    setSuggestions([]);
    setValidationIssues([]);
    setError(null);
    console.log(`Created new session: ${newSessionId}`);
  };

  const handleSessionChange = async (newSessionId: string) => {
    console.log(`Switching to session: ${newSessionId}`);
    setSessionId(newSessionId);
    // Clear current state while loading new session
    setSuggestions([]);
    setValidationIssues([]);
    // Chat history will be loaded by the useEffect dependency on sessionId
  };

  const formatMessageTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return '';

    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();

    if (isToday) {
      return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } else {
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: 'var(--bg-primary)' }}>
      {/* Left Panel: SQL Editor */}
      <div style={{ flex: '0 0 50%', padding: '20px', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>SQL Editor</h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={executeSQL}
              disabled={!sql.trim() || suggestionsLoading}
              style={{
                padding: '6px 12px',
                fontSize: '13px',
                backgroundColor: 'var(--primary)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: sql.trim() && !suggestionsLoading ? 'pointer' : 'not-allowed',
                opacity: sql.trim() && !suggestionsLoading ? 1 : 0.5,
              }}
            >
              {suggestionsLoading ? '⏳ Analyzing...' : '▶ Execute & Analyze'}
            </button>
            <button
              onClick={clearAll}
              style={{
                padding: '6px 12px',
                fontSize: '13px',
                backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              Clear
            </button>
          </div>
        </div>

        {/* SQL Textarea */}
        <textarea
          ref={sqlTextareaRef}
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          placeholder="Enter your SQL query here, or use the AI Chat to generate one..."
          style={{
            flex: 1,
            padding: '12px',
            fontSize: '14px',
            fontFamily: 'monospace',
            border: `1px solid ${validationIssues.length > 0 ? 'var(--error)' : 'var(--border-color)'}`,
            borderRadius: '6px',
            resize: 'none',
            outline: 'none',
          }}
        />

        {/* Quick Stats */}
        {schema && (
          <div style={{ marginTop: '12px', padding: '8px', backgroundColor: 'var(--bg-secondary)', borderRadius: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
            📊 Schema: {Object.keys(schema.tables).length} tables available
            {validationIssues.length > 0 && (
              <span style={{ marginLeft: '12px', color: 'var(--error)' }}>
                ⚠ {validationIssues.length} validation {validationIssues.length === 1 ? 'issue' : 'issues'}
              </span>
            )}
          </div>
        )}

        {/* Error/Success Message */}
        {error && (
          <div
            style={{
              marginTop: '12px',
              padding: '10px',
              backgroundColor: error.startsWith('✓') ? '#d4edda' : 'var(--error-bg)',
              color: error.startsWith('✓') ? '#155724' : 'var(--error)',
              borderRadius: '6px',
              fontSize: '13px',
            }}
          >
            {error}
          </div>
        )}
      </div>

      {/* Right Panel: Tabbed Interface */}
      <div style={{ flex: '0 0 50%', display: 'flex', flexDirection: 'column' }}>
        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', backgroundColor: 'var(--bg-secondary)' }}>
          <button
            onClick={() => setActiveTab('chat')}
            style={{
              flex: 1,
              padding: '12px',
              fontSize: '14px',
              fontWeight: activeTab === 'chat' ? '600' : '400',
              backgroundColor: activeTab === 'chat' ? 'var(--bg-primary)' : 'transparent',
              color: activeTab === 'chat' ? 'var(--primary)' : 'var(--text-secondary)',
              border: 'none',
              borderBottom: activeTab === 'chat' ? `2px solid var(--primary)` : 'none',
              cursor: 'pointer',
            }}
          >
            🤖 AI Chat
          </button>
          <button
            onClick={() => setActiveTab('suggestions')}
            style={{
              flex: 1,
              padding: '12px',
              fontSize: '14px',
              fontWeight: activeTab === 'suggestions' ? '600' : '400',
              backgroundColor: activeTab === 'suggestions' ? 'var(--bg-primary)' : 'transparent',
              color: activeTab === 'suggestions' ? 'var(--primary)' : 'var(--text-secondary)',
              border: 'none',
              borderBottom: activeTab === 'suggestions' ? `2px solid var(--primary)` : 'none',
              cursor: 'pointer',
            }}
          >
            💡 Suggestions {suggestions.length > 0 && `(${suggestions.length})`}
          </button>
          <button
            onClick={() => setActiveTab('validation')}
            style={{
              flex: 1,
              padding: '12px',
              fontSize: '14px',
              fontWeight: activeTab === 'validation' ? '600' : '400',
              backgroundColor: activeTab === 'validation' ? 'var(--bg-primary)' : 'transparent',
              color: activeTab === 'validation' ? (validationIssues.length > 0 ? 'var(--error)' : 'var(--primary)') : 'var(--text-secondary)',
              border: 'none',
              borderBottom: activeTab === 'validation' ? `2px solid ${validationIssues.length > 0 ? 'var(--error)' : 'var(--primary)'}` : 'none',
              cursor: 'pointer',
            }}
          >
            ✓ Validation {validationIssues.length > 0 && `(${validationIssues.length})`}
          </button>
        </div>

        {/* Tab Content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
          {activeTab === 'chat' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>AI SQL Assistant</h3>

                  {/* Chat History Dropdown */}
                  <ChatHistoryDropdown
                    dataSourceId={dataSourceId}
                    currentSessionId={sessionId}
                    onSessionChange={handleSessionChange}
                    onNewSession={handleNewSession}
                  />
                </div>

                {/* Semantic Search Input */}
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && searchChatHistory()}
                    placeholder="🔍 Search chat history..."
                    style={{
                      padding: '6px 10px',
                      fontSize: '12px',
                      width: '200px',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                      outline: 'none',
                    }}
                  />
                  <button
                    onClick={searchChatHistory}
                    disabled={!searchQuery.trim() || searchLoading}
                    style={{
                      padding: '6px 12px',
                      fontSize: '12px',
                      backgroundColor: 'var(--primary)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: searchQuery.trim() && !searchLoading ? 'pointer' : 'not-allowed',
                      opacity: searchQuery.trim() && !searchLoading ? 1 : 0.5,
                    }}
                  >
                    {searchLoading ? '⏳' : 'Search'}
                  </button>
                  {showSearchResults && (
                    <button
                      onClick={clearSearch}
                      style={{
                        padding: '6px 10px',
                        fontSize: '12px',
                        backgroundColor: 'var(--bg-secondary)',
                        color: 'var(--text-primary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: 'pointer',
                      }}
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>

              {/* Search Results (if showing) */}
              {showSearchResults ? (
                <div style={{ flex: 1, overflow: 'auto', marginBottom: '16px', backgroundColor: 'var(--bg-secondary)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '12px', color: 'var(--text-secondary)' }}>
                    Search Results ({searchResults.length} found)
                  </div>
                  {searchResults.length === 0 ? (
                    <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '20px' }}>
                      No messages found matching "{searchQuery}"
                    </div>
                  ) : (
                    searchResults.map((result, idx) => (
                      <div
                        key={idx}
                        style={{
                          marginBottom: '12px',
                          padding: '10px 12px',
                          backgroundColor: result.role === 'user' ? '#e3f2fd' : 'white',
                          borderRadius: '6px',
                          borderLeft: result.role === 'user' ? '3px solid var(--primary)' : '3px solid #4caf50',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <div style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                            {result.role === 'user' ? 'You' : '🤖 Assistant'}
                          </div>
                          <div style={{ fontSize: '10px', color: '#10b981', fontWeight: '600' }}>
                            {Math.round((result.similarity_score || 0) * 100)}% match
                          </div>
                        </div>
                        <MessageRenderer content={result.content} role={result.role} />
                        <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '6px' }}>
                          {new Date(result.timestamp).toLocaleString()}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                // Chat Messages (normal view)
                <div style={{ flex: 1, overflow: 'auto', marginBottom: '16px', backgroundColor: 'var(--bg-secondary)', borderRadius: '6px', padding: '12px' }}>
                {!historyLoaded && (
                  <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '40px 20px' }}>
                    <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
                    <p style={{ fontSize: '14px' }}>Loading chat history...</p>
                  </div>
                )}

                {historyLoaded && chatHistory.length === 0 && (
                  <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '40px 20px' }}>
                    <p style={{ fontSize: '14px', marginBottom: '12px' }}>👋 Welcome! I can help you:</p>
                    <ul style={{ textAlign: 'left', fontSize: '13px', lineHeight: '1.8' }}>
                      <li>Generate SQL from natural language</li>
                      <li>Optimize existing queries</li>
                      <li>Explain errors and suggest fixes</li>
                      <li>Create missing tables automatically</li>
                    </ul>
                    <p style={{ fontSize: '12px', marginTop: '16px' }}>Try: "Show all students enrolled in 2020"</p>
                  </div>
                )}

                {chatHistory.map((msg, idx) => {
                  // Render MCP suggestion card
                  if (msg.type === 'mcp_card' && msg.suggestion) {
                    const suggestion = msg.suggestion;
                    const getRiskColor = (risk: string) => {
                      switch (risk) {
                        case 'low': return '#10b981';
                        case 'medium': return '#f59e0b';
                        case 'high': return '#ef4444';
                        case 'critical': return '#991b1b';
                        default: return '#6b7280';
                      }
                    };

                    return (
                      <div
                        key={idx}
                        style={{
                          marginBottom: '12px',
                          padding: '12px',
                          backgroundColor: '#f0f9ff',
                          borderRadius: '6px',
                          borderLeft: `4px solid ${getRiskColor(suggestion.risk_level)}`,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '4px', color: '#1e40af' }}>
                              💡 {suggestion.description}
                            </div>
                            <div style={{ fontSize: '11px', color: '#6b7280', marginBottom: '6px' }}>
                              Tool: {suggestion.mcp_tool} • Risk: <span style={{ color: getRiskColor(suggestion.risk_level), fontWeight: '600' }}>{suggestion.risk_level.toUpperCase()}</span>
                            </div>
                          </div>
                          <div style={{ fontSize: '10px', padding: '2px 6px', backgroundColor: suggestion.status === 'executed' ? '#d1fae5' : '#e5e7eb', color: suggestion.status === 'executed' ? '#065f46' : '#374151', borderRadius: '4px', whiteSpace: 'nowrap' }}>
                            {suggestion.status}
                          </div>
                        </div>

                        {suggestion.rationale && (
                          <div style={{ fontSize: '12px', color: '#4b5563', marginBottom: '8px' }}>
                            {suggestion.rationale}
                          </div>
                        )}

                        {suggestion.sql && (
                          <pre style={{ fontSize: '11px', backgroundColor: '#1e1e1e', color: '#d4d4d4', padding: '8px', borderRadius: '4px', overflow: 'auto', marginBottom: '8px', margin: 0 }}>
                            {suggestion.sql}
                          </pre>
                        )}

                        {suggestion.warnings && suggestion.warnings.length > 0 && (
                          <div style={{ fontSize: '11px', color: '#ef4444', marginBottom: '8px' }}>
                            ⚠️ {suggestion.warnings.join(', ')}
                          </div>
                        )}

                        <div style={{ display: 'flex', gap: '8px' }}>
                          {suggestion.status === 'pending_approval' && (
                            <>
                              <button
                                onClick={() => approveMcpSuggestion(suggestion)}
                                style={{
                                  padding: '6px 14px',
                                  fontSize: '12px',
                                  backgroundColor: '#10b981',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontWeight: '500',
                                }}
                              >
                                ✅ Approve
                              </button>
                              <button
                                onClick={() => rejectMcpSuggestion(suggestion)}
                                style={{
                                  padding: '6px 14px',
                                  fontSize: '12px',
                                  backgroundColor: '#ef4444',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontWeight: '500',
                                }}
                              >
                                ❌ Reject
                              </button>
                            </>
                          )}
                          {suggestion.status === 'approved' && (
                            <button
                              onClick={() => executeMcpSuggestion(suggestion)}
                              disabled={executingMcp === suggestion.id}
                              style={{
                                padding: '6px 14px',
                                fontSize: '12px',
                                backgroundColor: '#3b82f6',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: executingMcp === suggestion.id ? 'not-allowed' : 'pointer',
                                opacity: executingMcp === suggestion.id ? 0.5 : 1,
                                fontWeight: '500',
                              }}
                            >
                              {executingMcp === suggestion.id ? '⏳ Executing...' : '⚡ Execute'}
                            </button>
                          )}
                          {suggestion.status === 'executed' && (
                            <div style={{ fontSize: '12px', color: '#10b981', fontWeight: '600' }}>
                              ✅ Executed Successfully
                            </div>
                          )}
                          {suggestion.status === 'rejected' && (
                            <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '600' }}>
                              ❌ Rejected
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  }

                  // Render normal chat message
                  return (
                    <div
                      key={idx}
                      style={{
                        marginBottom: '12px',
                        padding: '10px 12px',
                        backgroundColor: msg.role === 'user' ? '#e3f2fd' : 'white',
                        borderRadius: '6px',
                        borderLeft: msg.role === 'user' ? '3px solid var(--primary)' : '3px solid #4caf50',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <div style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                          {msg.role === 'user' ? 'You' : '🤖 Assistant'}
                        </div>
                        {msg.timestamp && (
                          <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                            {formatMessageTimestamp(msg.timestamp)}
                          </div>
                        )}
                      </div>
                      <MessageRenderer content={msg.content} role={msg.role} />
                    </div>
                  );
                })}

                {chatLoading && (
                  <div style={{ textAlign: 'center', padding: '12px', color: 'var(--text-secondary)' }}>
                    <div>⏳ AI is thinking...</div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>
              )}

              {/* Chat Input */}
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && sendChatMessage()}
                  placeholder="Ask me anything about SQL..."
                  disabled={chatLoading}
                  style={{
                    flex: 1,
                    padding: '10px 12px',
                    fontSize: '14px',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    outline: 'none',
                  }}
                />
                <button
                  onClick={sendChatMessage}
                  disabled={!chatInput.trim() || chatLoading}
                  style={{
                    padding: '10px 20px',
                    fontSize: '14px',
                    backgroundColor: 'var(--primary)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: chatInput.trim() && !chatLoading ? 'pointer' : 'not-allowed',
                    opacity: chatInput.trim() && !chatLoading ? 1 : 0.5,
                  }}
                >
                  Send
                </button>
              </div>
            </div>
          )}

          {activeTab === 'suggestions' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>Optimization Suggestions</h3>
                {suggestions.length === 0 && (
                  <button
                    onClick={analyzeSQLSuggestions}
                    disabled={!sql.trim() || suggestionsLoading}
                    style={{
                      padding: '6px 12px',
                      fontSize: '13px',
                      backgroundColor: 'var(--primary)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: sql.trim() && !suggestionsLoading ? 'pointer' : 'not-allowed',
                      opacity: sql.trim() && !suggestionsLoading ? 1 : 0.5,
                    }}
                  >
                    Analyze Query
                  </button>
                )}
              </div>

              {suggestions.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '40px 20px' }}>
                  <p>No suggestions yet.</p>
                  <p style={{ fontSize: '13px', marginTop: '8px' }}>Execute a query to get AI-powered optimization suggestions.</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {suggestions.map((suggestion) => (
                    <div
                      key={suggestion.id}
                      style={{
                        padding: '12px',
                        backgroundColor: 'var(--bg-secondary)',
                        borderRadius: '6px',
                        borderLeft: `3px solid ${
                          suggestion.category === 'index' ? '#8b5cf6' :
                          suggestion.category === 'rewrite' ? '#f59e0b' :
                          'var(--primary)'
                        }`,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                        <div>
                          <div style={{ fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                            {suggestion.category}
                          </div>
                          <div style={{ fontSize: '14px', fontWeight: '600', marginBottom: '4px' }}>
                            {suggestion.title}
                          </div>
                        </div>
                        {suggestion.sql_fix && (
                          <button
                            onClick={() => applySuggestion(suggestion)}
                            style={{
                              padding: '4px 10px',
                              fontSize: '12px',
                              backgroundColor: 'var(--primary)',
                              color: 'white',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            Apply
                          </button>
                        )}
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        {suggestion.summary}
                      </div>
                      {suggestion.sql_fix && (
                        <pre style={{
                          fontSize: '12px',
                          backgroundColor: '#1e1e1e',
                          color: '#d4d4d4',
                          padding: '8px',
                          borderRadius: '4px',
                          overflow: 'auto',
                          margin: 0,
                        }}>
                          {suggestion.sql_fix}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'validation' && (
            <div>
              <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: '600' }}>Query Validation</h3>

              {validationIssues.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#10b981', padding: '40px 20px' }}>
                  <div style={{ fontSize: '48px', marginBottom: '12px' }}>✓</div>
                  <p style={{ fontSize: '14px', fontWeight: '600' }}>No validation issues found</p>
                  <p style={{ fontSize: '13px', marginTop: '8px', color: 'var(--text-secondary)' }}>
                    {sql.trim() ? 'Your query looks good!' : 'Enter a query to validate'}
                  </p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {validationIssues.map((issue, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '12px',
                        backgroundColor: issue.type === 'syntax' || issue.type === 'missing_table' ? 'var(--error-bg)' : '#fff3cd',
                        borderRadius: '6px',
                        borderLeft: `3px solid ${issue.type === 'syntax' || issue.type === 'missing_table' ? 'var(--error)' : '#ffc107'}`,
                      }}
                    >
                      <div style={{ fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                        {issue.type}
                      </div>
                      <div style={{ fontSize: '14px', fontWeight: '600', marginBottom: '6px', color: issue.type === 'syntax' || issue.type === 'missing_table' ? 'var(--error)' : '#856404' }}>
                        {issue.message}
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                        💡 {issue.suggestion}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
