// Shared channel for optimization results so the Optimize DB / Optimize Table
// actions in the schema explorer can surface their suggestions in the (wider)
// AI Assistant panel instead of inline under the tree.

import { createContext, useContext, useState, type ReactNode } from 'react';

export interface OptimizationResult {
  type: 'database' | 'table';
  dsId: string;
  data: any;
}

interface OptimizationContextValue {
  result: OptimizationResult | null;
  loading: boolean;
  setResult: (r: OptimizationResult | null) => void;
  setLoading: (b: boolean) => void;
  /** Bumped (per datasource) to ask the matching schema explorer to reload. */
  refreshSignal: { dsId: string; nonce: number } | null;
  requestRefresh: (dsId: string) => void;
}

const OptimizationContext = createContext<OptimizationContextValue | null>(null);

export function OptimizationProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshSignal, setRefreshSignal] = useState<{ dsId: string; nonce: number } | null>(null);

  const requestRefresh = (dsId: string) =>
    setRefreshSignal((prev) => ({ dsId, nonce: (prev?.nonce ?? 0) + 1 }));

  return (
    <OptimizationContext.Provider
      value={{ result, loading, setResult, setLoading, refreshSignal, requestRefresh }}
    >
      {children}
    </OptimizationContext.Provider>
  );
}

export function useOptimization(): OptimizationContextValue {
  const ctx = useContext(OptimizationContext);
  if (!ctx) throw new Error('useOptimization must be used within OptimizationProvider');
  return ctx;
}
