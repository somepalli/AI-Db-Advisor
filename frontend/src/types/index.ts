// API Types
export interface DataSource {
  id: string;
  engine: string;
  dsn: string;
}

export interface DataSourceCreate {
  id: string;
  engine: string;
  dsn: string;
}

export interface TableSchema {
  column: string;
  type: string;
  nullable: string;
}

export interface SchemaResponse {
  tables: Record<string, TableSchema[]>;
}

export interface TopQuery {
  query: string;
  calls: number;
  mean_time_ms: number;
  rows: number;
  source: string;
}

export interface Lock {
  locktype: string;
  mode: string;
  granted: boolean;
  pid: number;
  age: string;
}

export interface Stats {
  total_db_size: number;
  active_backends: number;
}

export interface ExplainPlan {
  plan: any[];
}

export interface Recommendation {
  category: string;
  summary: string;
  sql_fix?: string;
  risk?: string;
  expected_gain?: string;
  details?: any;
}

export interface HypoIndexRequest {
  table: string;
  columns: string[];
  include?: string[];
  method?: string;
}

export interface HypoIndexResponse {
  hypo_stmt: string;
  hypopg_available: boolean;
}

export interface AIAdviceResponse {
  suggestions: Array<{
    type: string;
    summary: string;
    rationale?: string;
    new_sql?: string;
    sql_fix?: string;
    expected_gain?: string;
    validated?: boolean;
    risk?: string;
  }>;
}
