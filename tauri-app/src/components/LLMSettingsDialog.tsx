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
import { SiOllama, SiOpenai, SiAnthropic } from 'react-icons/si';
import type { IconType } from 'react-icons';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful save so the parent can refresh its status badge. */
  onSaved?: () => void;
}

interface ProviderDef {
  value: string;
  label: string;
  Logo: IconType;
  color: string;
}

const PROVIDERS: ProviderDef[] = [
  { value: 'ollama', label: 'Ollama', Logo: SiOllama, color: '#000000' },
  { value: 'openai', label: 'OpenAI', Logo: SiOpenai, color: '#412991' },
  { value: 'anthropic', label: 'Anthropic', Logo: SiAnthropic, color: '#D97757' },
];

const ENDPOINT_HINTS: Record<string, string> = {
  ollama: 'http://127.0.0.1:11434',
  openai: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com/v1',
};

// Suggested models per provider for the dropdown. The model field stays editable,
// so users can type any model not listed here.
const MODELS: Record<string, string[]> = {
  ollama: ['qwen2.5:7b-instruct', 'llama3.1:8b', 'mistral:7b', 'codellama:7b'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini', 'o3', 'o4-mini'],
  anthropic: ['claude-opus-4-8', 'claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5'],
};

const ALL_KNOWN_MODELS = new Set(Object.values(MODELS).flat());

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
  const [trustOverride, setTrustOverride] = useState<'' | 'local' | 'hosted'>('');
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
        setTrustOverride(cfg.provider_trust_override ?? '');
      })
      .catch((e) => setError(e?.message || 'Failed to load current LLM config'));
  }, [open]);

  const needsKey = provider === 'openai' || provider === 'anthropic';
  // Mirror the backend's resolve_provider_trust() so the UI can preview the effective trust.
  const resolvedTrust: 'local' | 'hosted' =
    trustOverride || (provider === 'ollama' ? 'local' : 'hosted');
  const payload = () => ({
    provider,
    endpoint: endpoint.trim(),
    model: model.trim(),
    // Empty string => leave the saved key untouched.
    api_key: apiKey || undefined,
    provider_trust: trustOverride, // "" = auto
  });

  // Switching provider via a logo tile: default the endpoint, and swap the model
  // to that provider's default if the current one belongs to a different provider.
  const selectProvider = (value: string) => {
    setProvider(value);
    setProbe(null);
    if (!endpoint || Object.values(ENDPOINT_HINTS).includes(endpoint)) {
      setEndpoint(ENDPOINT_HINTS[value] || '');
    }
    const belongsToOtherProvider =
      ALL_KNOWN_MODELS.has(model) && !(MODELS[value] || []).includes(model);
    if (!model || belongsToOtherProvider) {
      setModel((MODELS[value] || [])[0] ?? '');
    }
  };

  // Provider-specific suggestions + any models discovered via Test (Ollama).
  const modelOptions = Array.from(
    new Set([...(MODELS[provider] || []), ...(probe?.models || [])])
  );

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
            <Label>Provider</Label>
            <div className="grid grid-cols-3 gap-2">
              {PROVIDERS.map((p) => {
                const active = provider === p.value;
                return (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => selectProvider(p.value)}
                    title={p.label}
                    className={`flex flex-col items-center justify-center gap-1.5 rounded-md border p-3 h-20 transition-colors ${
                      active ? 'border-primary border-2 bg-primary/5' : 'border-border hover:bg-accent'
                    }`}
                  >
                    <p.Logo size={26} color={p.color} className="dark:invert" />
                    <span className="text-xs">{p.label}</span>
                  </button>
                );
              })}
            </div>
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
              placeholder={`e.g. ${(MODELS[provider] || [])[0] ?? 'model name'}`}
              onChange={(e) => setModel(e.target.value)}
            />
            {/* Provider-specific suggestions (+ installed Ollama models from Test).
                The field stays editable — type any model not listed here. */}
            <datalist id="llm-model-options">
              {modelOptions.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
            <p className="text-xs text-muted-foreground">
              Pick a {PROVIDERS.find((p) => p.value === provider)?.label} model, or type your own.
            </p>
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

          <div className="grid gap-1.5">
            <Label htmlFor="llm-trust">Data access</Label>
            <Select value={trustOverride || 'auto'} onValueChange={(v) => setTrustOverride(v === 'auto' ? '' : (v as 'local' | 'hosted'))}>
              <SelectTrigger id="llm-trust">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">Auto (from provider)</SelectItem>
                <SelectItem value="local">Force local (full access)</SelectItem>
                <SelectItem value="hosted">Force hosted (metadata only)</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Effective: <span className="font-medium">{resolvedTrust}</span>.{' '}
              {resolvedTrust === 'hosted'
                ? 'Hosted models get schema + sanitized metadata only — never sample rows.'
                : 'Local models may read sample rows and run data tools.'}
            </p>
          </div>

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
