// Alert rule management + monitoring lifecycle API.
import { API_BASE_URL } from './client';

export interface AlertCondition {
  metric: string;
  operator: string;
  threshold: number;
  duration_minutes?: number;
}

export interface AlertRule {
  id: string;
  name: string;
  severity: string; // "P1" | "P2" | "P3"
  description: string;
  enabled: boolean;
  datasource_types: string[];
  conditions: AlertCondition[];
  auto_resolve: boolean;
  cooldown_minutes: number;
}

export interface AlertRulesResponse {
  rules: AlertRule[];
  count: number;
}

export interface MonitoringStatus {
  monitored_datasources?: string[];
  [key: string]: unknown;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`Request failed (${response.status}): ${detail}`);
  }
  return response.json() as Promise<T>;
}

export const alertRulesApi = {
  list: (): Promise<AlertRulesResponse> => request<AlertRulesResponse>('/alerts/rules'),

  create: (rule: AlertRule): Promise<any> =>
    request('/alerts/rules', { method: 'POST', body: JSON.stringify(rule) }),

  update: (ruleId: string, rule: AlertRule): Promise<any> =>
    request(`/alerts/rules/${encodeURIComponent(ruleId)}`, {
      method: 'PUT',
      body: JSON.stringify(rule),
    }),

  remove: (ruleId: string): Promise<any> =>
    request(`/alerts/rules/${encodeURIComponent(ruleId)}`, { method: 'DELETE' }),

  startMonitoring: (dsId: string): Promise<any> =>
    request(`/alerts/monitoring/${encodeURIComponent(dsId)}/start`, { method: 'POST' }),

  stopMonitoring: (dsId: string): Promise<any> =>
    request(`/alerts/monitoring/${encodeURIComponent(dsId)}/stop`, { method: 'POST' }),

  monitoringStatus: (): Promise<MonitoringStatus> =>
    request<MonitoringStatus>('/alerts/monitoring/status'),
};
