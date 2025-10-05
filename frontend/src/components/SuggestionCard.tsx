import { useState } from 'react';
import type { Suggestion } from '../types/suggestions';

interface Props {
  suggestion: Suggestion;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
  onApply: (id: string) => void;
}

export function SuggestionCard({ suggestion, isSelected, onToggleSelect, onApply }: Props) {
  const [showSqlFix, setShowSqlFix] = useState(false);

  const copyToClipboard = (text: string) => {
    // Windows line endings
    const windowsText = text.replace(/\n/g, '\r\n');
    navigator.clipboard.writeText(windowsText);
  };

  // Badge colors
  const levelColors = {
    db: '#8b5cf6',
    table: '#3b82f6',
    query: '#06b6d4',
  };

  const confidenceColors = {
    'rule-based': '#f59e0b',
    'ai-heuristic': '#8b5cf6',
    'validated': '#10b981',
  };

  const riskColors = {
    low: '#10b981',
    medium: '#f59e0b',
    high: '#ef4444',
  };

  return (
    <div
      style={{
        padding: '16px',
        backgroundColor: isSelected ? '#eff6ff' : 'var(--bg-secondary)',
        borderRadius: '8px',
        marginBottom: '12px',
        border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-color)',
        transition: 'all 0.2s',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', marginBottom: '12px' }}>
        {/* Checkbox */}
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggleSelect(suggestion.id)}
          style={{
            width: '18px',
            height: '18px',
            cursor: 'pointer',
            marginTop: '2px',
          }}
        />

        {/* Title and Summary */}
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: '600', fontSize: '15px', marginBottom: '6px' }}>
            {suggestion.title}
          </div>
          <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
            {suggestion.summary}
          </div>

          {/* Badges */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {/* Level */}
            <span
              style={{
                padding: '3px 8px',
                fontSize: '12px',
                borderRadius: '4px',
                backgroundColor: levelColors[suggestion.level],
                color: 'white',
                fontWeight: '500',
              }}
            >
              {suggestion.level.toUpperCase()}
            </span>

            {/* Category */}
            <span
              style={{
                padding: '3px 8px',
                fontSize: '12px',
                borderRadius: '4px',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                fontWeight: '500',
              }}
            >
              {suggestion.category}
            </span>

            {/* Confidence */}
            <span
              style={{
                padding: '3px 8px',
                fontSize: '12px',
                borderRadius: '4px',
                backgroundColor: confidenceColors[suggestion.confidence],
                color: 'white',
                fontWeight: '500',
              }}
            >
              {suggestion.confidence}
            </span>

            {/* Validated */}
            <span
              style={{
                padding: '3px 8px',
                fontSize: '12px',
                borderRadius: '4px',
                backgroundColor: suggestion.validated ? '#10b981' : '#9ca3af',
                color: 'white',
                fontWeight: '500',
              }}
            >
              {suggestion.validated ? '✓ Validated' : '✗ Not Validated'}
            </span>

            {/* Risk */}
            <span
              style={{
                padding: '3px 8px',
                fontSize: '12px',
                borderRadius: '4px',
                backgroundColor: riskColors[suggestion.risk],
                color: 'white',
                fontWeight: '500',
              }}
            >
              {suggestion.risk.toUpperCase()} RISK
            </span>
          </div>

          {/* Estimated Gain */}
          {suggestion.estimated_gain && (
            <div style={{ marginTop: '8px', fontSize: '13px', color: '#10b981', fontWeight: '500' }}>
              💡 {suggestion.estimated_gain}
            </div>
          )}

          {/* Related Objects */}
          {suggestion.related_objects.length > 0 && (
            <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              📦 Affects: {suggestion.related_objects.join(', ')}
            </div>
          )}
        </div>
      </div>

      {/* SQL Fix (collapsible) */}
      {suggestion.sql_fix && (
        <div style={{ marginTop: '12px' }}>
          <button
            onClick={() => setShowSqlFix(!showSqlFix)}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              backgroundColor: 'var(--primary)',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: '500',
            }}
          >
            {showSqlFix ? '▼ Hide SQL' : '▶ Show SQL'}
          </button>

          {showSqlFix && (
            <div
              style={{
                marginTop: '8px',
                padding: '12px',
                backgroundColor: '#1e293b',
                color: '#e2e8f0',
                borderRadius: '6px',
                fontFamily: 'monospace',
                fontSize: '13px',
                whiteSpace: 'pre-wrap',
                position: 'relative',
              }}
            >
              <button
                onClick={() => copyToClipboard(suggestion.sql_fix!)}
                style={{
                  position: 'absolute',
                  top: '8px',
                  right: '8px',
                  padding: '4px 8px',
                  fontSize: '11px',
                  backgroundColor: '#475569',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                📋 Copy
              </button>
              {suggestion.sql_fix}
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
        <button
          onClick={() => onApply(suggestion.id)}
          style={{
            padding: '8px 16px',
            fontSize: '13px',
            backgroundColor: suggestion.validated ? '#10b981' : '#f59e0b',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: '600',
          }}
        >
          ⚡ Apply
        </button>
      </div>
    </div>
  );
}
