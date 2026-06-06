// Database engine catalog: brand logos, default ports, structured connection
// fields, and DSN builders. The Add-Connection UI collects host/port/user/etc.
// as separate inputs and assembles the DSN here, so users never type a raw DSN.

import type { IconType } from 'react-icons';
import {
  SiPostgresql,
  SiMysql,
  SiMongodb,
  SiRedis,
  SiApachecassandra,
  SiClickhouse,
  SiSqlite,
  SiDuckdb,
} from 'react-icons/si';
import { DiMsqlServer } from 'react-icons/di';
import { FaDatabase } from 'react-icons/fa';

export type FieldKey = 'host' | 'port' | 'database' | 'username' | 'password' | 'file';

export interface EngineField {
  key: FieldKey;
  label: string;
  placeholder?: string;
  required?: boolean;
  type?: 'text' | 'password' | 'number';
}

export interface EngineDef {
  /** Canonical engine value sent to the backend. */
  value: string;
  label: string;
  /** Brand logo (omitted when no trademark-clear icon exists -> monogram fallback). */
  Logo?: IconType;
  color: string;
  category: 'SQL' | 'NoSQL';
  /** Shown as a top-level logo tile (vs. tucked under "Other"). */
  featured?: boolean;
  defaultPort?: number;
  fields: EngineField[];
  buildDsn: (v: Record<string, string>) => string;
}

const enc = (s: string) => encodeURIComponent(s ?? '');

/** scheme://user:pass@  (or user@, or empty when no username given). */
function authority(v: Record<string, string>): string {
  if (!v.username) return '';
  return v.password ? `${enc(v.username)}:${enc(v.password)}@` : `${enc(v.username)}@`;
}

/** Standard host/port/database/username/password field set. */
function netFields(
  port: number,
  dbLabel = 'Database',
  opts: { username?: boolean; password?: boolean } = {}
): EngineField[] {
  const fields: EngineField[] = [
    { key: 'host', label: 'Host', placeholder: 'localhost', required: true },
    { key: 'port', label: 'Port', placeholder: String(port), required: true, type: 'number' },
    { key: 'database', label: dbLabel, placeholder: dbLabel.toLowerCase(), required: true },
  ];
  if (opts.username !== false) {
    fields.push({ key: 'username', label: 'Username', placeholder: 'user' });
  }
  if (opts.password !== false) {
    fields.push({ key: 'password', label: 'Password', type: 'password' });
  }
  return fields;
}

export const DB_ENGINES: EngineDef[] = [
  {
    value: 'postgres',
    label: 'PostgreSQL',
    Logo: SiPostgresql,
    color: '#336791',
    category: 'SQL',
    featured: true,
    defaultPort: 5432,
    fields: netFields(5432),
    buildDsn: (v) => `postgresql://${authority(v)}${v.host}:${v.port}/${enc(v.database)}`,
  },
  {
    value: 'mysql',
    label: 'MySQL / MariaDB',
    Logo: SiMysql,
    color: '#4479A1',
    category: 'SQL',
    featured: true,
    defaultPort: 3306,
    fields: netFields(3306),
    buildDsn: (v) => `mysql://${authority(v)}${v.host}:${v.port}/${enc(v.database)}`,
  },
  {
    value: 'mongodb',
    label: 'MongoDB',
    Logo: SiMongodb,
    color: '#47A248',
    category: 'NoSQL',
    featured: true,
    defaultPort: 27017,
    fields: netFields(27017),
    buildDsn: (v) => `mongodb://${authority(v)}${v.host}:${v.port}/${enc(v.database)}`,
  },
  {
    value: 'redis',
    label: 'Redis',
    Logo: SiRedis,
    color: '#DC382D',
    category: 'NoSQL',
    featured: true,
    defaultPort: 6379,
    // Redis has no username; "database" is a numeric DB index.
    fields: [
      { key: 'host', label: 'Host', placeholder: 'localhost', required: true },
      { key: 'port', label: 'Port', placeholder: '6379', required: true, type: 'number' },
      { key: 'database', label: 'DB index', placeholder: '0', required: true, type: 'number' },
      { key: 'password', label: 'Password', type: 'password' },
    ],
    buildDsn: (v) =>
      `redis://${v.password ? `:${enc(v.password)}@` : ''}${v.host}:${v.port}/${v.database || '0'}`,
  },
  {
    value: 'sqlserver',
    label: 'SQL Server',
    Logo: DiMsqlServer,
    color: '#CC2927',
    category: 'SQL',
    featured: true,
    defaultPort: 1433,
    fields: netFields(1433),
    buildDsn: (v) => `mssql://${authority(v)}${v.host}:${v.port}/${enc(v.database)}`,
  },

  // ---- "Other" engines (shown in the dropdown) ----
  {
    value: 'oracle',
    label: 'Oracle',
    // Oracle has no trademark-clear icon in the icon sets -> monogram fallback.
    color: '#F80000',
    category: 'SQL',
    defaultPort: 1521,
    fields: netFields(1521, 'Service name'),
    buildDsn: (v) => `oracle://${authority(v)}${v.host}:${v.port}/${enc(v.database)}`,
  },
  {
    value: 'cassandra',
    label: 'Cassandra',
    Logo: SiApachecassandra,
    color: '#1287B1',
    category: 'NoSQL',
    defaultPort: 9042,
    fields: netFields(9042, 'Keyspace'),
    buildDsn: (v) => `cassandra://${authority(v)}${v.host}:${v.port}/${enc(v.database)}`,
  },
  {
    value: 'clickhouse',
    label: 'ClickHouse',
    Logo: SiClickhouse,
    color: '#FFCC01',
    category: 'SQL',
    defaultPort: 8123,
    fields: netFields(8123),
    buildDsn: (v) => `clickhouse://${authority(v)}${v.host}:${v.port}/${enc(v.database)}`,
  },
  {
    value: 'sqlite',
    label: 'SQLite',
    Logo: SiSqlite,
    color: '#003B57',
    category: 'SQL',
    // File-based: a single path, no host/port/auth.
    fields: [
      {
        key: 'file',
        label: 'Database file path',
        placeholder: 'C:/data/myapp.db',
        required: true,
      },
    ],
    buildDsn: (v) => `sqlite:///${v.file}`,
  },
  {
    value: 'duckdb',
    label: 'DuckDB',
    Logo: SiDuckdb,
    color: '#FFF000',
    category: 'SQL',
    fields: [
      {
        key: 'file',
        label: 'Database file path',
        placeholder: 'C:/data/myapp.duckdb',
        required: true,
      },
    ],
    buildDsn: (v) => `duckdb:///${v.file}`,
  },
];

/** Aliases the backend accepts -> our canonical engine value (for rendering saved rows). */
const ALIASES: Record<string, string> = {
  postgresql: 'postgres',
  pg: 'postgres',
  mariadb: 'mysql',
  mssql: 'sqlserver',
  'sql-server': 'sqlserver',
  mongo: 'mongodb',
  'oracle-db': 'oracle',
  'cassandra-db': 'cassandra',
  sqlite3: 'sqlite',
  'clickhouse+http': 'clickhouse',
  'clickhouse+https': 'clickhouse',
};

export const FEATURED_ENGINES = DB_ENGINES.filter((e) => e.featured);
export const OTHER_ENGINES = DB_ENGINES.filter((e) => !e.featured);

export function getEngineDef(engine: string): EngineDef | undefined {
  const key = (engine || '').toLowerCase();
  const canonical = ALIASES[key] ?? key;
  return DB_ENGINES.find((e) => e.value === canonical);
}

/** Initial field values for an engine: localhost + default port pre-filled. */
export function initialValues(engine: string): Record<string, string> {
  const def = getEngineDef(engine);
  const values: Record<string, string> = {};
  if (!def) return values;
  for (const f of def.fields) {
    if (f.key === 'host') values.host = 'localhost';
    else if (f.key === 'port') values.port = String(def.defaultPort ?? '');
    else if (f.key === 'database' && def.value === 'redis') values.database = '0';
    else values[f.key] = '';
  }
  return values;
}

/** Brand logo for an engine; falls back to a colored monogram tile. */
export function EngineLogo({
  engine,
  size = 22,
}: {
  engine: string;
  size?: number;
}) {
  const def = getEngineDef(engine);
  if (!def) return <FaDatabase size={size} color="#6b7280" />;
  if (def.Logo) return <def.Logo size={size} color={def.color} title={def.label} />;
  return (
    <span
      aria-label={def.label}
      title={def.label}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        borderRadius: 5,
        background: def.color,
        color: 'white',
        fontSize: size * 0.6,
        fontWeight: 700,
        lineHeight: 1,
      }}
    >
      {def.label[0]}
    </span>
  );
}
