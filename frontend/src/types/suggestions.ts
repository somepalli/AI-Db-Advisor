export type Level = "db" | "table" | "query";
export type Category = "index" | "rewrite" | "config" | "partition" | "cleanup" | "note";
export type Confidence = "rule-based" | "ai-heuristic" | "validated";
export type Risk = "low" | "medium" | "high";

export interface Suggestion {
  id: string;
  level: Level;
  category: Category;
  title: string;
  summary: string;
  sql_fix?: string | null;
  validated: boolean;
  confidence: Confidence;
  risk: Risk;
  estimated_gain?: string | null;
  related_objects: string[];
  metadata: Record<string, unknown>;
}

export interface AnalyzeSuggestionsRequest {
  ds_id: string;
  sql: string;
  include_ai?: boolean;
  top_k?: number;
}

export interface AnalyzeSuggestionsResponse {
  notes: string[];
  suggestions: Suggestion[];
}

export interface ApplySuggestionsRequest {
  ds_id: string;
  suggestion_ids: string[];
  dry_run?: boolean;
}

export interface ApplySuggestionsDirectRequest {
  ds_id: string;
  suggestions: Suggestion[];
  dry_run?: boolean;
}

export interface ApplyResult {
  id: string;
  status: "success" | "skipped" | "error";
  message: string;
  rollback_sql?: string | null;
}

export interface ApplySuggestionsResponse {
  notes: string[];
  results: ApplyResult[];
}

export interface ApplyHistoryItem {
  timestamp: string;
  ds_id: string;
  suggestion_ids: string[];
  dry_run: boolean;
  results: ApplyResult[];
}
