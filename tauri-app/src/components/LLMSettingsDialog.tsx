import { useEffect, useState } from 'react';
import { llmApi, type LLMStatus } from '../api/client';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Button } from './ui/button';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful save so the parent can refresh its status badge. */
  onSaved?: () => void;
}

const PROVIDERS = [
  { value: 'ollama', label: 'Ollama (local)' },
  { value: 'openai', label: 'OpenAI-compatible' },
  { value: 'anthropic', label: 'Anthropic (Claude)' },
];

const ENDPOINT_HINTS: Record<string, string> = {
  ollama: 'http://127.0.0.1:11434',
  openai: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com/v1',
};

/**
 * Lets the user point the app at a different LLM (provider / endpoint / model / API key)
 * from the UI instead of editing the .env file. Changes are saved on the backend and
 * applied immediately to all subsequent requests.
 */
export function LLMSettingsDialog({ open, onOpenChange, onSaved }: Props) {
  const [provider, setProvider] = useState('ollama');
  const [endpoint, setEndpoint] = useState('');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [hasSavedKey, setHasSavedKey] = useState(false);
  const [probe, setProbe] = useState<LLMStatus | null>(null);
  const [busy, setBusy] = useState<'test' | 'save' | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load the current saved config each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setError(null);
    setProbe(null);
    setApiKey('');
    llmApi
      .getConfig()
      .then((cfg) => {
        setProvider(cfg.provider);
        setEndpoint(cfg.endpoint);
        setModel(cfg.model);
        setHasSavedKey(cfg.has_api_key);
      })
      .catch((e) => setError(e?.message || 'Failed to load current LLM config'));
  }, [open]);

  const needsKey = provider === 'openai' || provider === 'anthropic';
  const payload = () => ({
    provider,
    endpoint: endpoint.trim(),
    model: model.trim(),
    // Empty string => leave the saved key untouched.
    api_key: apiKey || undefined,
  });

  const handleTest = async () => {
    setBusy('test');
    setError(null);
    try {
      setProbe(await llmApi.test(payload()));
    } catch (e: any) {
      setError(e?.message || 'Test failed');
    } finally {
      setBusy(null);
    }
  };

  const handleSave = async () => {
    setBusy('save');
    setError(null);
    try {
      const status = await llmApi.updateConfig(payload());
      setProbe(status);
      onSaved?.();
      onOpenChange(false);
    } catch (e: any) {
      setError(e?.message || 'Save failed');
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>LLM Connection</DialogTitle>
          <DialogDescription>
            Choose which language model the app uses. Changes apply immediately — no .env edit or
            restart needed.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-1.5">
            <Label htmlFor="llm-provider">Provider</Label>
            <Select
              value={provider}
              onValueChange={(v) => {
                setProvider(v);
                // Offer a sensible default endpoint when switching providers.
                if (!endpoint || Object.values(ENDPOINT_HINTS).includes(endpoint)) {
                  setEndpoint(ENDPOINT_HINTS[v] || '');
                }
              }}
            >
              <SelectTrigger id="llm-provider">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROVIDERS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="llm-endpoint">Endpoint</Label>
            <Input
              id="llm-endpoint"
              value={endpoint}
              placeholder={ENDPOINT_HINTS[provider]}
              onChange={(e) => setEndpoint(e.target.value)}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="llm-model">Model</Label>
            <Input
              id="llm-model"
              value={model}
              list="llm-model-options"
              placeholder="e.g. qwen2.5:7b-instruct"
              onChange={(e) => setModel(e.target.value)}
            />
            {/* Populated from a successful Test so users can pick an installed model. */}
            <datalist id="llm-model-options">
              {(probe?.models || []).map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </div>

          {needsKey && (
            <div className="grid gap-1.5">
              <Label htmlFor="llm-api-key">API key</Label>
              <Input
                id="llm-api-key"
                type="password"
                value={apiKey}
                placeholder={hasSavedKey ? '•••••• (saved — leave blank to keep)' : 'Required for this provider'}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
          )}

          {probe && (
            <div
              className={`text-xs rounded-md border px-3 py-2 ${
                probe.connected
                  ? 'border-green-500/30 text-green-700 bg-green-500/10'
                  : 'border-red-500/30 text-red-700 bg-red-500/10'
              }`}
            >
              {probe.connected ? '🟢 ' : '🔴 '}
              {probe.detail}
            </div>
          )}

          {error && (
            <div className="text-xs rounded-md border border-red-500/30 text-red-700 bg-red-500/10 px-3 py-2">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleTest} disabled={busy !== null}>
            {busy === 'test' ? 'Testing…' : 'Test connection'}
          </Button>
          <Button onClick={handleSave} disabled={busy !== null}>
            {busy === 'save' ? 'Saving…' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
