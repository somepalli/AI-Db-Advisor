import { useEffect, useState } from 'react';
import { llmApi, type LLMStatus } from '../api/client';
import { LLMSettingsDialog } from './LLMSettingsDialog';

/**
 * Small header badge showing which LLM the app is talking to and whether it's
 * reachable, e.g. "🟢 ollama · qwen2.5:7b-instruct". Polls periodically so the
 * dot turns green as soon as a local LLM comes up, without a page reload.
 * Clicking it opens the LLM connection settings so users can switch providers
 * from the UI (no .env edit required).
 */
export function LLMStatusBadge() {
  const [status, setStatus] = useState<LLMStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const refresh = async () => {
    try {
      setStatus(await llmApi.status());
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000); // re-check every 15s
    return () => clearInterval(id);
  }, []);

  const connected = !!status?.connected;
  const dot = loading ? '⚪' : connected ? '🟢' : '🔴';
  const label = loading
    ? 'Checking LLM…'
    : status
      ? `${status.provider}${status.model ? ' · ' + status.model : ''}`
      : 'LLM unavailable';
  const title = `${status?.detail || 'Could not reach the backend to check LLM status'} — click to change`;

  return (
    <>
      <div
        title={title}
        onClick={() => setSettingsOpen(true)}
        className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full cursor-pointer select-none border ${
          connected
            ? 'border-green-500/30 text-green-600 bg-green-500/10'
            : 'border-red-500/30 text-red-600 bg-red-500/10'
        }`}
      >
        <span>{dot}</span>
        <span className="font-medium">{label}</span>
        <span className="opacity-60">⚙</span>
      </div>
      <LLMSettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        onSaved={refresh}
      />
    </>
  );
}
