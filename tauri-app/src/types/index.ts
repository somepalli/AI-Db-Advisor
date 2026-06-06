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
  pk?: boolean;
}

export interface SchemaResponse {
  tables: Record<string, TableSchema[]>;
}

export interface DbFunction {
  name: string;
  kind: string; // function | procedure | aggregate | window
  returns?: string;
  arguments?: string;
}

export interface DbTrigger {
  name: string;
  table: string;
  timing?: string; // BEFORE | AFTER | INSTEAD OF
  events?: string; // INSERT, UPDATE, ...
}

export interface DatabaseObjects {
  database: string;
  tables: Record<string, TableSchema[]>;
  views: Record<string, TableSchema[]>;
  sequences: string[];
  functions: DbFunction[];
  triggers: DbTrigger[];
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
