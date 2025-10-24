// API client using native fetch (works in Tauri v2 with proper permissions)
import type {
  DataSource,
  DataSourceCreate,
  SchemaResponse,
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

const API_BASE_URL = 'http://127.0.0.1:8000';

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
