import { Fragment, useState, useEffect } from 'react';
import { analyzeApi, optimizationApi } from '../api/client';
import type { DatabaseObjects, TableSchema } from '../types';
import { useOptimization } from '../lib/optimizationContext';
import { Button } from './ui/button';
import {
  ChevronRight,
  Database,
  Table2,
  Eye,
  Hash,
  Braces,
  Workflow,
  KeyRound,
  Columns3,
  Zap,
  Sparkles,
  RefreshCw,
} from 'lucide-react';

interface Props {
  dataSourceId: string;
}

/** A single row in the object tree (folder or leaf). */
function TreeRow({
  depth,
  icon,
  label,
  meta,
  hasChildren,
  open,
  onClick,
  action,
  title,
}: {
  depth: number;
  icon: React.ReactNode;
  label: React.ReactNode;
  meta?: React.ReactNode;
  hasChildren?: boolean;
  open?: boolean;
  onClick?: () => void;
  action?: React.ReactNode;
  title?: string;
}) {
  return (
    <div
      onClick={onClick}
      title={title}
      className="group flex items-center gap-1.5 py-1 pr-1 rounded hover:bg-accent cursor-pointer select-none"
      style={{ paddingLeft: depth * 14 + 4 }}
    >
      {hasChildren ? (
        <ChevronRight
          className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform ${
            open ? 'rotate-90' : ''
          }`}
        />
      ) : (
        <span className="w-3.5 shrink-0" />
      )}
      <span className="shrink-0 flex items-center">{icon}</span>
      <span className="text-sm truncate flex-1 text-left">{label}</span>
      {meta != null && (
        <span className="text-[10px] text-muted-foreground shrink-0">{meta}</span>
      )}
      {action}
    </div>
  );
}

const shortName = (n: string) => (n.startsWith('public.') ? n.slice('public.'.length) : n);

export function DBExplorer({ dataSourceId }: Props) {
  const [objects, setObjects] = useState<DatabaseObjects | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tree expansion state
  const [dbOpen, setDbOpen] = useState(true);
  const [openCats, setOpenCats] = useState<Set<string>>(new Set(['tables']));
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  // Optimization: results are surfaced in the AI Assistant panel via shared context.
  const optimization = useOptimization();
  const [optimizationLoading, setOptimizationLoading] = useState(false);

  useEffect(() => {
    if (dataSourceId) {
      loadObjects();
    } else {
      setLoading(false);
      setObjects(null);
    }
  }, [dataSourceId]);

  // Reload when an apply (from the AI Assistant) targets this datasource.
  useEffect(() => {
    if (optimization.refreshSignal?.dsId === dataSourceId) {
      loadObjects();
    }
  }, [optimization.refreshSignal]);

  const loadObjects = async () => {
    if (!dataSourceId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await analyzeApi.getObjects(dataSourceId);
      setObjects(data);
      setError(null);
    } catch (err) {
      console.error('❌ Schema load error:', err);
      setError('Failed to load schema: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const toggleCat = (key: string) =>
    setOpenCats((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const toggleTable = (name: string) =>
    setExpandedTables((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const handleOptimizeDatabase = async () => {
    try {
      setOptimizationLoading(true);
      optimization.setLoading(true);
      setError(null);
      const result = await optimizationApi.optimizeDatabase(dataSourceId);
      optimization.setResult({ type: 'database', dsId: dataSourceId, data: result });
    } catch (err) {
      setError('Failed to optimize database: ' + (err as Error).message);
    } finally {
      setOptimizationLoading(false);
      optimization.setLoading(false);
    }
  };

  const handleOptimizeTable = async (tableName: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Don't expand/collapse the table row
    try {
      setOptimizationLoading(true);
      optimization.setLoading(true);
      setError(null);
      const shortTableName = tableName.split('.').pop() || tableName;
      const result = await optimizationApi.optimizeTable(dataSourceId, shortTableName);
      optimization.setResult({ type: 'table', dsId: dataSourceId, data: result });
    } catch (err) {
      setError('Failed to optimize table: ' + (err as Error).message);
    } finally {
      setOptimizationLoading(false);
      optimization.setLoading(false);
    }
  };

  if (!dataSourceId) return null;

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground">
        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
        Loading schema...
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-2 py-2">
        <div className="bg-destructive/10 text-destructive text-xs p-2 rounded-md">{error}</div>
        <Button onClick={loadObjects} variant="outline" size="sm" className="w-full mt-2 text-xs">
          <RefreshCw className="h-3 w-3 mr-1" />
          Retry
        </Button>
      </div>
    );
  }

  const o = objects;
  const tableEntries: [string, TableSchema[]][] = o ? Object.entries(o.tables) : [];
  const viewEntries: [string, TableSchema[]][] = o ? Object.entries(o.views || {}) : [];
  const sequences = o?.sequences ?? [];
  const functions = o?.functions ?? [];
  const triggers = o?.triggers ?? [];

  const renderColumns = (cols: TableSchema[]) =>
    cols.map((col, i) => (
      <TreeRow
        key={i}
        depth={3}
        icon={
          col.pk ? (
            <KeyRound className="h-3.5 w-3.5 text-amber-500" />
          ) : (
            <Columns3 className="h-3.5 w-3.5 text-muted-foreground" />
          )
        }
        label={col.column}
        meta={`${col.type}${col.nullable === 'NO' ? ' · NN' : ''}`}
        title={`${col.column} — ${col.type}${col.pk ? ' (PK)' : ''}${
          col.nullable === 'NO' ? ' NOT NULL' : ''
        }`}
      />
    ));

  return (
    <div className="pb-1">
      {/* pgAdmin-style object tree (database -> categories -> objects) */}
      <div className="text-foreground">
        <TreeRow
          depth={0}
          icon={<Database className="h-4 w-4 text-primary" />}
          label={<span className="font-semibold">{o?.database}</span>}
          hasChildren
          open={dbOpen}
          onClick={() => setDbOpen(!dbOpen)}
          action={
            <div className="flex items-center gap-0.5 shrink-0">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleOptimizeDatabase();
                }}
                disabled={optimizationLoading}
                title="Optimize database"
                className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-primary/10"
              >
                {optimizationLoading ? (
                  <RefreshCw className="h-3 w-3 animate-spin text-primary" />
                ) : (
                  <Sparkles className="h-3 w-3 text-primary" />
                )}
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  loadObjects();
                }}
                title="Refresh"
                className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-accent"
              >
                <RefreshCw className="h-3 w-3 text-muted-foreground" />
              </button>
            </div>
          }
        />

          {dbOpen && (
            <>
              {/* Tables */}
              <TreeRow
                depth={1}
                icon={<Table2 className="h-3.5 w-3.5 text-sky-600" />}
                label="Tables"
                meta={tableEntries.length}
                hasChildren
                open={openCats.has('tables')}
                onClick={() => toggleCat('tables')}
              />
              {openCats.has('tables') &&
                tableEntries.map(([name, cols]) => (
                  <Fragment key={name}>
                    <TreeRow
                      depth={2}
                      icon={<Table2 className="h-3.5 w-3.5 text-sky-600" />}
                      label={shortName(name)}
                      meta={cols.length}
                      hasChildren
                      open={expandedTables.has(name)}
                      onClick={() => toggleTable(name)}
                      title={name}
                      action={
                        <button
                          type="button"
                          onClick={(e) => handleOptimizeTable(name, e)}
                          disabled={optimizationLoading}
                          title="Optimize table"
                          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-primary/10 shrink-0"
                        >
                          <Zap className="h-3 w-3 text-primary" />
                        </button>
                      }
                    />
                    {expandedTables.has(name) && renderColumns(cols)}
                  </Fragment>
                ))}

              {/* Views */}
              <TreeRow
                depth={1}
                icon={<Eye className="h-3.5 w-3.5 text-violet-500" />}
                label="Views"
                meta={viewEntries.length}
                hasChildren
                open={openCats.has('views')}
                onClick={() => toggleCat('views')}
              />
              {openCats.has('views') &&
                viewEntries.map(([name, cols]) => (
                  <Fragment key={name}>
                    <TreeRow
                      depth={2}
                      icon={<Eye className="h-3.5 w-3.5 text-violet-500" />}
                      label={shortName(name)}
                      meta={cols.length}
                      hasChildren
                      open={expandedTables.has(name)}
                      onClick={() => toggleTable(name)}
                      title={name}
                    />
                    {expandedTables.has(name) && renderColumns(cols)}
                  </Fragment>
                ))}

              {/* Sequences */}
              <TreeRow
                depth={1}
                icon={<Hash className="h-3.5 w-3.5 text-emerald-600" />}
                label="Sequences"
                meta={sequences.length}
                hasChildren
                open={openCats.has('sequences')}
                onClick={() => toggleCat('sequences')}
              />
              {openCats.has('sequences') &&
                sequences.map((seq) => (
                  <TreeRow
                    key={seq}
                    depth={2}
                    icon={<Hash className="h-3.5 w-3.5 text-emerald-600" />}
                    label={shortName(seq)}
                    title={seq}
                  />
                ))}

              {/* Functions / Procedures */}
              <TreeRow
                depth={1}
                icon={<Braces className="h-3.5 w-3.5 text-orange-500" />}
                label="Functions / Procedures"
                meta={functions.length}
                hasChildren
                open={openCats.has('functions')}
                onClick={() => toggleCat('functions')}
              />
              {openCats.has('functions') &&
                functions.map((fn, i) => (
                  <TreeRow
                    key={`${fn.name}-${i}`}
                    depth={2}
                    icon={<Braces className="h-3.5 w-3.5 text-orange-500" />}
                    label={shortName(fn.name)}
                    meta={fn.kind}
                    title={`${fn.name}(${fn.arguments ?? ''})${
                      fn.returns ? ` → ${fn.returns}` : ''
                    }`}
                  />
                ))}

              {/* Triggers */}
              <TreeRow
                depth={1}
                icon={<Workflow className="h-3.5 w-3.5 text-rose-500" />}
                label="Triggers"
                meta={triggers.length}
                hasChildren
                open={openCats.has('triggers')}
                onClick={() => toggleCat('triggers')}
              />
              {openCats.has('triggers') &&
                triggers.map((trg, i) => (
                  <TreeRow
                    key={`${trg.name}-${i}`}
                    depth={2}
                    icon={<Workflow className="h-3.5 w-3.5 text-rose-500" />}
                    label={shortName(trg.name)}
                    meta={trg.table}
                    title={`${trg.timing ?? ''} ${trg.events ?? ''} on ${trg.table}`}
                  />
                ))}
            </>
          )}
        </div>

      </div>
  );
}
