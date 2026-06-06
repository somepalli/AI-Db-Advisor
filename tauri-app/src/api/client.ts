// API client using native fetch (works in Tauri v2 with proper permissions)
import type {
  DataSource,
  DataSourceCreate,
  SchemaResponse,
  DatabaseObjects,
  TopQuery,
  Lock,
  Stats,
  ExplainPlan,
  Recommendation,
  HypoIndexRequest,
  HypoIndexResponse,
  AIAdviceResponse,
} from '../types';
import type {
  AnalyzeSuggestionsRequest,
  AnalyzeSuggestionsResponse,
  ApplySuggestionsRequest,
  ApplySuggestionsDirectRequest,
  ApplySuggestionsResponse,
} from '../types/suggestions';

// Re-export commonly used types so consumers can import them from the client.
export type { DataSource } from '../types';

// Base URL for the backend API. Override at build/run time with VITE_API_BASE_URL.
export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://127.0.0.1:8095';

// Helper function for API requests
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.statusText}`);
  }

  return response.json();
}

// Health & Root API
export const healthApi = {
  healthz: async (): Promise<{ status: string }> => {
    return apiRequest<{ status: string }>('/healthz');
  },

  root: async (): Promise<{ message: string; version?: string }> => {
    return apiRequest<{ message: string; version?: string }>('/');
  },
};

// LLM status API
export interface LLMStatus {
  provider: string;
  model: string;
  endpoint: string;
  connected: boolean;
  models: string[];
  detail: string;
}

// Current saved LLM config (the API key is never returned, only whether one is set).
export interface LLMConfig {
  provider: string;
  model: string;
  endpoint: string;
  has_api_key: boolean;
  // Resolved data-access trust ("local" | "hosted") and the saved override ("" = auto).
  provider_trust: 'local' | 'hosted';
  provider_trust_override: '' | 'local' | 'hosted';
}

// Partial update — omit a field to leave it unchanged.
export interface LLMConfigUpdate {
  provider?: string;
  model?: string;
  endpoint?: string;
  api_key?: string;
  // "" = auto-derive from provider, "local"/"hosted" = force.
  provider_trust?: '' | 'local' | 'hosted';
}

export const llmApi = {
  status: async (): Promise<LLMStatus> => {
    return apiRequest<LLMStatus>('/llm/status');
  },

  getConfig: async (): Promise<LLMConfig> => {
    return apiRequest<LLMConfig>('/llm/config');
  },

  // Probe a candidate config without saving it (the "Test connection" button).
  test: async (cfg: LLMConfigUpdate): Promise<LLMStatus> => {
    return apiRequest<LLMStatus>('/llm/test', {
      method: 'POST',
      body: JSON.stringify(cfg),
    });
  },

  // Persist a new config; takes effect immediately for all subsequent requests.
  updateConfig: async (cfg: LLMConfigUpdate): Promise<LLMStatus> => {
    return apiRequest<LLMStatus>('/llm/config', {
      method: 'PUT',
      body: JSON.stringify(cfg),
    });
  },
};

// Datasources API
export const datasourcesApi = {
  list: async (): Promise<Record<string, DataSource>> => {
    const response = await apiRequest<{ items: DataSource[] }>('/datasources');
    // Convert array to Record<id, datasource>
    const record: Record<string, DataSource> = {};
    response.items.forEach((ds) => {
      record[ds.id] = ds;
    });
    return record;
  },

  create: async (data: DataSourceCreate): Promise<{ message: string }> => {
    return apiRequest<{ message: string }>('/datasources', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  delete: async (dsId: string): Promise<{ ok: boolean; message: string }> => {
    return apiRequest<{ ok: boolean; message: string }>(`/datasources/${dsId}`, {
      method: 'DELETE',
    });
  },
};

// Analyze API
export const analyzeApi = {
  getSchema: async (dsId: string): Promise<SchemaResponse> => {
    return apiRequest<SchemaResponse>(`/analyze/${dsId}/schema`);
  },

  getObjects: async (dsId: string): Promise<DatabaseObjects> => {
    return apiRequest<DatabaseObjects>(`/analyze/${dsId}/objects`);
  },

  getTopQueries: async (dsId: string, limit: number = 10): Promise<TopQuery[]> => {
    return apiRequest<TopQuery[]>(`/analyze/${dsId}/top?limit=${limit}`);
  },

  explain: async (dsId: string, sql: string, analyze: boolean = false): Promise<ExplainPlan> => {
    return apiRequest<ExplainPlan>(`/analyze/${dsId}/explain`, {
      method: 'POST',
      body: JSON.stringify({ sql, analyze }),
    });
  },

  getLocks: async (dsId: string): Promise<Lock[]> => {
    return apiRequest<Lock[]>(`/analyze/${dsId}/locks`);
  },

  getStats: async (dsId: string): Promise<Stats> => {
    return apiRequest<Stats>(`/analyze/${dsId}/stats`);
  },

  adviseIndex: async (dsId: string, sql: string): Promise<Recommendation[]> => {
    return apiRequest<Recommendation[]>(`/analyze/${dsId}/advise/index`, {
      method: 'POST',
      body: JSON.stringify({ sql, analyze: false }),
    });
  },

  adviseRewrite: async (dsId: string, sql: string): Promise<Recommendation[]> => {
    return apiRequest<Recommendation[]>(`/analyze/${dsId}/advise/rewrite`, {
      method: 'POST',
      body: JSON.stringify({ sql, analyze: false }),
    });
  },

  adviseAI: async (dsId: string, sql: string): Promise<AIAdviceResponse> => {
    return apiRequest<AIAdviceResponse>(`/analyze/${dsId}/advise/ai`, {
      method: 'POST',
      body: JSON.stringify({ sql, analyze: false }),
    });
  },

  hypoIndex: async (dsId: string, request: HypoIndexRequest): Promise<HypoIndexResponse> => {
    return apiRequest<HypoIndexResponse>(`/analyze/${dsId}/hypo-index`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  explainPlanAI: async (dsId: string, sql: string, analyze: boolean = false): Promise<AIAdviceResponse> => {
    return apiRequest<AIAdviceResponse>(`/analyze/${dsId}/explain/ai`, {
      method: 'POST',
      body: JSON.stringify({ sql, analyze }),
    });
  },

  executeQuery: async (dsId: string, sql: string): Promise<{
    columns: string[];
    rows: Record<string, any>[];
    row_count: number;
    status: string;
    error?: { type: string; message: string; details?: string };
  }> => {
    return apiRequest(`/analyze/${dsId}/execute`, {
      method: 'POST',
      body: JSON.stringify({ sql, analyze: false }),
    });
  },
};

// Suggestions API (Optimizer Workflow)
export const suggestionsApi = {
  analyze: async (request: AnalyzeSuggestionsRequest): Promise<AnalyzeSuggestionsResponse> => {
    return apiRequest<AnalyzeSuggestionsResponse>('/suggestions/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  apply: async (request: ApplySuggestionsRequest): Promise<ApplySuggestionsResponse> => {
    return apiRequest<ApplySuggestionsResponse>('/suggestions/apply', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  applyDirect: async (request: ApplySuggestionsDirectRequest): Promise<ApplySuggestionsResponse> => {
    return apiRequest<ApplySuggestionsResponse>('/suggestions/apply_direct', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },
};

// Optimization API
export const optimizationApi = {
  optimizeDatabase: async (dsId: string): Promise<any> => {
    return apiRequest<any>(`/analyze/${dsId}/optimize/database`, {
      method: 'POST',
    });
  },

  optimizeTable: async (dsId: string, tableName: string): Promise<any> => {
    return apiRequest<any>(`/analyze/${dsId}/optimize/table/${tableName}`, {
      method: 'POST',
    });
  },

  applyOptimizations: async (dsId: string, sqlStatements: string[]): Promise<any> => {
    return apiRequest<any>(`/analyze/${dsId}/optimize/apply`, {
      method: 'POST',
      body: JSON.stringify({ sql_statements: sqlStatements }),
    });
  },
};

// AI Chat API
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  ds_id: string;
  message: string;
  conversation_history?: ChatMessage[];
  current_sql?: string;
  session_id?: string;          // For chat history persistence
  save_to_history?: boolean;    // Auto-save to vector DB (default: true)
}

export interface ChatResponse {
  message: string;
  sql?: string;
  suggestions: Array<{
    type: string;
    summary: string;
    sql?: string;
    rationale?: string;
  }>;
  action: string;
  context: Record<string, any>;
}

export interface ValidateQueryRequest {
  ds_id: string;
  sql: string;
}

export interface ValidateQueryResponse {
  valid: boolean;
  issues: Array<{
    type: string;
    message: string;
    suggestion: string;
  }>;
  missing_tables: string[];
  has_conditions: boolean;
  suggestions: string[];
}

export const aiChatApi = {
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    return apiRequest<ChatResponse>('/ai-chat/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Streaming chat endpoint - returns async generator that yields tokens
   *
   * Usage:
   * ```typescript
   * const stream = aiChatApi.chatStream({...});
   * for await (const chunk of stream) {
   *   if (chunk.type === 'token') {
   *     // Append chunk.content to display
   *   } else if (chunk.type === 'done') {
   *     // Stream complete
   *   }
   * }
   * ```
   */
  chatStream: async function* (request: ChatRequest): AsyncGenerator<{type: string; content?: string; message?: string}> {
    const response = await fetch(`${API_BASE_URL}/ai-chat/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Streaming failed: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages (separated by \n\n)
        const messages = buffer.split('\n\n');
        buffer = messages.pop() || ''; // Keep incomplete message in buffer

        for (const message of messages) {
          if (message.startsWith('data: ')) {
            const jsonStr = message.substring(6); // Remove 'data: ' prefix
            try {
              const data = JSON.parse(jsonStr);
              yield data;

              if (data.type === 'done' || data.type === 'error') {
                return; // End generator
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', jsonStr, e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  validateQuery: async (request: ValidateQueryRequest): Promise<ValidateQueryResponse> => {
    return apiRequest<ValidateQueryResponse>('/ai-chat/validate-query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },
};

// Chat History API
export interface SaveMessageRequest {
  ds_id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  sql_context?: string;
  message_id?: string;
}

export interface SaveMessageResponse {
  message_id: string;
  success: boolean;
}

export interface HistoryMessage {
  message_id: string;
  ds_id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  sql_context?: string;
  timestamp: string;
}

export interface GetHistoryResponse {
  messages: HistoryMessage[];
  total: number;
  ds_id: string;
}

export interface SearchMessagesRequest {
  ds_id: string;
  query: string;
  limit?: number;
  session_id?: string;
}

export interface SearchMessagesResponse {
  results: Array<HistoryMessage & { similarity_score: number }>;
  query: string;
  total: number;
}

export interface StatsResponse {
  ds_id: string;
  total_messages: number;
  total_sessions: number;
  user_messages: number;
  assistant_messages: number;
  collection_name: string;
}

export const chatHistoryApi = {
  saveMessage: async (request: SaveMessageRequest): Promise<SaveMessageResponse> => {
    return apiRequest<SaveMessageResponse>('/chat-history/save', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  getHistory: async (dsId: string, sessionId?: string, limit: number = 50): Promise<GetHistoryResponse> => {
    const params = new URLSearchParams();
    if (sessionId) params.append('session_id', sessionId);
    params.append('limit', limit.toString());

    const query = params.toString() ? `?${params.toString()}` : '';
    return apiRequest<GetHistoryResponse>(`/chat-history/${dsId}${query}`);
  },

  getSession: async (dsId: string, sessionId: string): Promise<GetHistoryResponse> => {
    return apiRequest<GetHistoryResponse>(`/chat-history/${dsId}/session/${sessionId}`);
  },

  searchMessages: async (request: SearchMessagesRequest): Promise<SearchMessagesResponse> => {
    return apiRequest<SearchMessagesResponse>('/chat-history/search', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  deleteHistory: async (dsId: string): Promise<{ success: boolean; message: string }> => {
    return apiRequest<{ success: boolean; message: string }>(`/chat-history/${dsId}`, {
      method: 'DELETE',
    });
  },

  deleteSession: async (dsId: string, sessionId: string): Promise<{ success: boolean; deleted_count: number }> => {
    return apiRequest<{ success: boolean; deleted_count: number }>(`/chat-history/${dsId}/session/${sessionId}`, {
      method: 'DELETE',
    });
  },

  getStats: async (dsId: string): Promise<StatsResponse> => {
    return apiRequest<StatsResponse>(`/chat-history/${dsId}/stats`);
  },
};

// MCP (Model Context Protocol) API
export interface MCPSuggestion {
  id: string;
  approval_id?: string;
  mcp_tool: string;
  sql: string;
  description: string;
  rationale: string;
  category: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  impact_level?: 'minimal' | 'moderate' | 'significant' | 'massive';
  warnings: string[];
  blocking_issues?: string[];
  tables_affected: string[];
  is_reversible: boolean;
  requires_backup: boolean;
  requires_confirmation: boolean;
  requires_double_confirmation?: boolean;
  recommendation: string;
  impact_details?: any;
  status: 'generated' | 'validated' | 'pending_approval' | 'approved' | 'rejected' | 'executing' | 'executed' | 'failed';
  generated_at: string;
  validated_at?: string;
}

export interface MCPSuggestionRequest {
  query?: string;
  schema_context?: any;
  optimization_type?: string;
  max_suggestions?: number;
}

export interface MCPSuggestionResponse {
  suggestions: MCPSuggestion[];
  count: number;
  datasource_id: string;
  requested_at: string;
  note: string;
  /** True when MCP is not configured and the suggestions are illustrative samples. */
  demo_mode?: boolean;
}

export interface ApprovalRequest {
  notes?: string;
}

export interface RejectRequest {
  reason: string;
}

export interface ApprovalResponse {
  success: boolean;
  message: string;
  approval: any;
}

export interface ExecutionResponse {
  success: boolean;
  message: string;
  approval_id: string;
  suggestion_id: string;
  result: any;
  executed_at: string;
}

export interface MCPStatistics {
  datasource_id: string;
  mcp_enabled: boolean;
  total_submitted: number;
  total_approved: number;
  total_rejected: number;
  total_executed: number;
  total_failed: number;
  currently_pending: number;
  awaiting_execution: number;
}

export const mcpApi = {
  // Request MCP suggestions
  requestSuggestions: async (dsId: string, request: MCPSuggestionRequest): Promise<MCPSuggestionResponse> => {
    return apiRequest<MCPSuggestionResponse>(`/mcp/${dsId}/request-suggestions`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // Approve a suggestion
  approve: async (dsId: string, approvalId: string, request: ApprovalRequest = {}, userId: string = 'user'): Promise<ApprovalResponse> => {
    return apiRequest<ApprovalResponse>(`/mcp/${dsId}/approve/${approvalId}`, {
      method: 'POST',
      headers: {
        'X-User-ID': userId,
      },
      body: JSON.stringify(request),
    });
  },

  // Reject a suggestion
  reject: async (dsId: string, approvalId: string, request: RejectRequest, userId: string = 'user'): Promise<ApprovalResponse> => {
    return apiRequest<ApprovalResponse>(`/mcp/${dsId}/reject/${approvalId}`, {
      method: 'POST',
      headers: {
        'X-User-ID': userId,
      },
      body: JSON.stringify(request),
    });
  },

  // Execute an approved suggestion
  execute: async (dsId: string, approvalId: string, userId: string = 'user'): Promise<ExecutionResponse> => {
    return apiRequest<ExecutionResponse>(`/mcp/${dsId}/execute/${approvalId}`, {
      method: 'POST',
      headers: {
        'X-User-ID': userId,
      },
    });
  },

  // Get pending approvals
  getPending: async (dsId: string): Promise<{ pending: any[]; count: number; datasource_id: string }> => {
    return apiRequest<{ pending: any[]; count: number; datasource_id: string }>(`/mcp/${dsId}/pending`);
  },

  // Get execution history
  getHistory: async (dsId: string, limit: number = 50, status?: string): Promise<{ history: any[]; count: number; datasource_id: string }> => {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    if (status) params.append('status', status);

    const query = params.toString() ? `?${params.toString()}` : '';
    return apiRequest<{ history: any[]; count: number; datasource_id: string }>(`/mcp/${dsId}/history${query}`);
  },

  // Get statistics
  getStatistics: async (dsId: string): Promise<MCPStatistics> => {
    return apiRequest<MCPStatistics>(`/mcp/${dsId}/statistics`);
  },

  // Health check
  healthCheck: async (): Promise<any> => {
    return apiRequest<any>('/mcp/health');
  },
};

// Analytics API (DuckDB)
export interface SyncTableRequest {
  pg_ds_id: string;
  duckdb_ds_id: string;
  table_name: string;
  batch_size?: number;
  incremental?: boolean;
  timestamp_column?: string;
}

export interface SyncAllTablesRequest {
  pg_ds_id: string;
  duckdb_ds_id: string;
  exclude_tables?: string[];
  batch_size?: number;
}

export interface SyncStatusRequest {
  pg_ds_id: string;
  duckdb_ds_id: string;
}

export interface AnalyticsQueryRequest {
  ds_id: string;
  query: string;
}

export interface SyncResult {
  success: boolean;
  table?: string;
  rows_synced?: number;
  sync_type?: string;
  tables_synced?: number;
  total_rows?: number;
  error?: string;
}

export interface SyncStatus {
  success: boolean;
  synced_tables: string[];
  unsynced_tables: string[];
  table_stats: Array<{
    table: string;
    pg_rows: number;
    duckdb_rows: number;
    in_sync: boolean;
  }>;
}

export interface AnalyticsResult {
  success: boolean;
  rows: Array<Record<string, any>>;
  row_count: number;
  error?: string;
}

// Alerts API
export interface AlertResponse {
  id: string;
  rule_id: string;
  severity: string;
  title: string;
  message: string;
  datasource_id: string;
  datasource_engine: string;
  triggered_at: string;
  status: string;
  metric_value?: any;
  threshold?: any;
  metadata?: Record<string, any>;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  auto_resolved: boolean;
  resolution_type?: string | null;
}

export interface AlertListResponse {
  alerts: AlertResponse[];
  count: number;
  summary?: Record<string, number>;
}

export const alertsApi = {
  getActive: async (): Promise<AlertListResponse> => {
    return apiRequest<AlertListResponse>('/alerts/active');
  },
  getResolved: async (limit = 50): Promise<AlertListResponse> => {
    return apiRequest<AlertListResponse>(`/alerts/resolved?limit=${limit}`);
  },
  getAll: async (limit = 100): Promise<AlertListResponse> => {
    return apiRequest<AlertListResponse>(`/alerts/all?limit=${limit}`);
  },
  acknowledge: async (id: string, payload: { acknowledged_by: string; notes?: string }): Promise<AlertResponse> => {
    return apiRequest<AlertResponse>(`/alerts/${encodeURIComponent(id)}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  resolve: async (id: string, payload: { resolved_by?: string; notes?: string }): Promise<AlertResponse> => {
    return apiRequest<AlertResponse>(`/alerts/${encodeURIComponent(id)}/resolve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  analyze: async (id: string): Promise<any> => {
    return apiRequest<any>(`/alerts/${encodeURIComponent(id)}/analyze`, {
      method: 'POST',
    });
  },
};

export const analyticsApi = {
  // Data sync endpoints
  syncTable: async (request: SyncTableRequest): Promise<SyncResult> => {
    return apiRequest<SyncResult>('/analytics/sync/table', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  syncAllTables: async (request: SyncAllTablesRequest): Promise<SyncResult> => {
    return apiRequest<SyncResult>('/analytics/sync/all', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  getSyncStatus: async (request: SyncStatusRequest): Promise<SyncStatus> => {
    return apiRequest<SyncStatus>('/analytics/sync/status', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // Analytics query endpoint
  query: async (request: AnalyticsQueryRequest): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>('/analytics/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // Pre-built analytics metrics
  getStudentEnrollmentMetrics: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/metrics/student-enrollment`);
  },

  getFeeCollectionMetrics: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/metrics/fee-collection`);
  },

  getLibraryUsageMetrics: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/metrics/library-usage`);
  },

  getHostelOccupancyMetrics: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/metrics/hostel-occupancy`);
  },

  getCoursePopularityMetrics: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/metrics/course-popularity`);
  },

  // Advanced dashboard analytics endpoints
  getDashboardKPIs: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/kpis`);
  },

  getEnrollmentTrends: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/enrollment-trends`);
  },

  getDepartmentDistribution: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/department-distribution`);
  },

  getGradeDistribution: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/grade-distribution`);
  },

  getRevenueAnalysis: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/revenue-analysis`);
  },

  getLibraryAnalytics: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/library-analytics`);
  },

  getPerformanceMetrics: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/performance-metrics`);
  },

  getHostelAnalytics: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/hostel-analytics`);
  },

  getComparativeAnalysis: async (dsId: string): Promise<AnalyticsResult> => {
    return apiRequest<AnalyticsResult>(`/analytics/${dsId}/dashboard/comparative-analysis`);
  },
};
