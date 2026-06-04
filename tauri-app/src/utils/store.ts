// Connection store.
//
// Secrets (full DSN strings, which contain passwords) are kept in the OS-native
// credential store via Tauri keyring commands (`secret_set` / `secret_get` /
// `secret_delete`). Only NON-secret metadata (id, engine, a password-redacted DSN
// for display) is kept in localStorage.
//
// When running outside Tauri (plain `vite dev` in a browser), the keyring is not
// available, so we fall back to localStorage and warn once — dev convenience only.

import { invoke } from '@tauri-apps/api/core';

export interface StoredConnection {
  id: string;
  engine: string;
  dsn: string; // full DSN (with secret) — only ever returned from getAll()/getFullDsn()
  createdAt: string;
}

interface ConnectionMeta {
  id: string;
  engine: string;
  dsnRedacted: string;
  createdAt: string;
}

const META_KEY = 'ai-db-advisor-connections';
const SECRET_PREFIX = 'dsn:';
const FALLBACK_SECRET_PREFIX = 'ai-db-advisor-secret:';

let warnedNoKeyring = false;

function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

function warnOnce(reason?: unknown): void {
  if (!warnedNoKeyring) {
    warnedNoKeyring = true;
    console.warn(
      '[store] OS keyring unavailable — falling back to localStorage for connection ' +
        'secrets (not encrypted at rest). This is expected under `vite dev`; under the ' +
        'desktop app it may indicate the OS secret service is unavailable.',
      reason ?? ''
    );
  }
}

/** Mask the password segment of a DSN: scheme://user:password@host -> scheme://user:***@host */
function redactDsn(dsn: string): string {
  return dsn.replace(/(:\/\/[^:/?#@]+:)[^@/?#]*(@)/, '$1***$2');
}

// --- secret backend (keyring with localStorage fallback) -------------------

async function secretSet(id: string, value: string): Promise<void> {
  const key = SECRET_PREFIX + id;
  if (isTauri()) {
    try {
      await invoke('secret_set', { key, value });
      return;
    } catch (e) {
      // Keyring unavailable at runtime (e.g. headless Linux with no Secret Service,
      // or called before Tauri internals are ready) — fall back rather than lose data.
      warnOnce(e);
    }
  } else {
    warnOnce();
  }
  localStorage.setItem(FALLBACK_SECRET_PREFIX + id, value);
}

async function secretGet(id: string): Promise<string | null> {
  const key = SECRET_PREFIX + id;
  if (isTauri()) {
    try {
      return (await invoke<string | null>('secret_get', { key })) ?? null;
    } catch (e) {
      warnOnce(e);
    }
  } else {
    warnOnce();
  }
  return localStorage.getItem(FALLBACK_SECRET_PREFIX + id);
}

async function secretDelete(id: string): Promise<void> {
  const key = SECRET_PREFIX + id;
  if (isTauri()) {
    try {
      await invoke('secret_delete', { key });
    } catch (e) {
      warnOnce(e);
    }
  }
  // Always clear any localStorage fallback copy too.
  localStorage.removeItem(FALLBACK_SECRET_PREFIX + id);
}

// --- metadata (localStorage) ----------------------------------------------

function readMetas(): ConnectionMeta[] {
  try {
    const raw = localStorage.getItem(META_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as any[];
    // Normalize legacy entries that stored a raw `dsn` field.
    return parsed.map((c) => ({
      id: c.id,
      engine: c.engine,
      dsnRedacted: c.dsnRedacted ?? (c.dsn ? redactDsn(c.dsn) : ''),
      createdAt: c.createdAt ?? new Date().toISOString(),
    }));
  } catch (error) {
    console.error('Failed to load connections:', error);
    return [];
  }
}

function writeMetas(metas: ConnectionMeta[]): void {
  localStorage.setItem(META_KEY, JSON.stringify(metas));
}

/**
 * One-time migration: older versions stored the full DSN (with password) in the
 * localStorage array. Move any such secret into the keyring and strip it from
 * localStorage.
 */
async function migrateLegacySecrets(): Promise<void> {
  let parsed: any[];
  try {
    const raw = localStorage.getItem(META_KEY);
    if (!raw) return;
    parsed = JSON.parse(raw);
  } catch {
    return;
  }
  // Only strip the raw `dsn` from localStorage for entries whose secret was
  // successfully stored — otherwise a transient keyring failure would permanently
  // destroy the only copy of the password. Un-migrated entries keep their raw dsn
  // so a later startup can retry.
  const migrated = new Set<string>();
  let sawLegacyDsn = false;
  for (const entry of parsed) {
    if (entry && typeof entry.dsn === 'string' && entry.dsn.length > 0) {
      sawLegacyDsn = true;
      try {
        if (!(await secretGet(entry.id))) {
          await secretSet(entry.id, entry.dsn);
        }
        migrated.add(entry.id);
      } catch (e) {
        console.error(`Failed to migrate secret for ${entry.id} (keeping raw dsn for retry):`, e);
      }
    }
  }

  if (!sawLegacyDsn) return;

  const cleaned = parsed.map((entry) => {
    if (migrated.has(entry.id)) {
      // Drop the raw secret; keep only redacted metadata.
      return {
        id: entry.id,
        engine: entry.engine,
        dsnRedacted: entry.dsnRedacted ?? (entry.dsn ? redactDsn(entry.dsn) : ''),
        createdAt: entry.createdAt ?? new Date().toISOString(),
      };
    }
    return entry; // preserve un-migrated entries (incl. raw dsn) untouched
  });
  localStorage.setItem(META_KEY, JSON.stringify(cleaned));
}

export const connectionStore = {
  /** Non-secret metadata for all saved connections (synchronous, safe to render). */
  getAllMeta: (): ConnectionMeta[] => readMetas(),

  /**
   * All saved connections with their full DSNs reassembled from the keyring.
   * Used at startup to re-register connections with the backend.
   */
  getAll: async (): Promise<StoredConnection[]> => {
    await migrateLegacySecrets();
    const metas = readMetas();
    const result: StoredConnection[] = [];
    for (const meta of metas) {
      const dsn = await secretGet(meta.id);
      if (dsn) {
        result.push({ id: meta.id, engine: meta.engine, dsn, createdAt: meta.createdAt });
      }
    }
    return result;
  },

  /** Persist a connection: secret DSN -> keyring, redacted metadata -> localStorage. */
  save: async (connection: Omit<StoredConnection, 'createdAt'>): Promise<void> => {
    try {
      await secretSet(connection.id, connection.dsn);
      const metas = readMetas();
      const meta: ConnectionMeta = {
        id: connection.id,
        engine: connection.engine,
        dsnRedacted: redactDsn(connection.dsn),
        createdAt: new Date().toISOString(),
      };
      const existingIndex = metas.findIndex((c) => c.id === connection.id);
      if (existingIndex >= 0) {
        metas[existingIndex] = meta;
      } else {
        metas.push(meta);
      }
      writeMetas(metas);
    } catch (error) {
      console.error('Failed to save connection:', error);
      throw new Error('Failed to save connection to secure storage');
    }
  },

  /** Remove a connection's metadata and its secret. */
  delete: async (id: string): Promise<void> => {
    try {
      await secretDelete(id);
      writeMetas(readMetas().filter((c) => c.id !== id));
    } catch (error) {
      console.error('Failed to delete connection:', error);
      throw new Error('Failed to delete connection from storage');
    }
  },

  /** Non-secret metadata for a single connection. */
  getById: (id: string): ConnectionMeta | null => readMetas().find((c) => c.id === id) || null,

  /** Full DSN (with secret) for a single connection, or null. */
  getFullDsn: async (id: string): Promise<string | null> => secretGet(id),

  /** Remove all metadata and secrets. */
  clear: async (): Promise<void> => {
    const metas = readMetas();
    for (const meta of metas) {
      await secretDelete(meta.id);
    }
    localStorage.removeItem(META_KEY);
  },
};
