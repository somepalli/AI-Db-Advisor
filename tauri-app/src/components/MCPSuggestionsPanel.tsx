/**
 * MCP Suggestions Panel - Google Model Context Protocol Integration
 *
 * Features:
 * - Request MCP suggestions for database optimization
 * - Display suggestions with risk indicators
 * - User approval workflow
 * - Safe execution with confirmations
 * - Audit trail
 */
import { useState } from 'react';
import { mcpApi, type MCPSuggestion, type MCPSuggestionRequest } from '../api/client';

interface Props {
  dataSourceId: string;
  currentQuery?: string;
}

// Risk level colors
const RISK_COLORS = {
  low: '#10b981',      // Green
  medium: '#f59e0b',   // Orange
  high: '#ef4444',     // Red
  critical: '#991b1b', // Dark Red
};

// Risk level emojis
const RISK_ICONS = {
  low: '🟢',
  medium: '🟡',
  high: '🟠',
  critical: '🔴',
};

export function MCPSuggestionsPanel({ dataSourceId, currentQuery }: Props) {
  const [suggestions, setSuggestions] = useState<MCPSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [selectedSuggestion, setSelectedSuggestion] = useState<MCPSuggestion | null>(null);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [showExecutionDialog, setShowExecutionDialog] = useState(false);
  const [confirmationText, setConfirmationText] = useState('');

  const requestSuggestions = async () => {
    setLoading(true);
    setError(null);

    try {
      const request: MCPSuggestionRequest = {
        query: currentQuery,
        optimization_type: 'general',
        max_suggestions: 5,
      };

      const response = await mcpApi.requestSuggestions(dataSourceId, request);

      setSuggestions(response.suggestions);
      setDemoMode(Boolean(response.demo_mode));
      setError(null);

      console.log(`Received ${response.count} MCP suggestions${response.demo_mode ? ' (demo mode)' : ''}`);
    } catch (err: any) {
      setError(err.message || 'Failed to request MCP suggestions');
      console.error('MCP request error:', err);
    } finally {
      setLoading(false);
    }
  };

  const approveSuggestion = async (suggestion: MCPSuggestion) => {
    setSelectedSuggestion(suggestion);
    setShowApprovalDialog(true);
  };

  const confirmApproval = async () => {
    if (!selectedSuggestion?.approval_id) return;

    try {
      await mcpApi.approve(
        dataSourceId,
        selectedSuggestion.approval_id,
        { notes: 'Approved via UI' },
        'user'
      );

      // Update suggestion status
      setSuggestions((prev) =>
        prev.map((s) =>
          s.id === selectedSuggestion.id ? { ...s, status: 'approved' } : s
        )
      );

      setShowApprovalDialog(false);
      setSelectedSuggestion(null);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to approve suggestion');
    }
  };

  const rejectSuggestion = async (suggestion: MCPSuggestion, reason: string) => {
    if (!suggestion.approval_id) return;

    try {
      await mcpApi.reject(
        dataSourceId,
        suggestion.approval_id,
        { reason },
        'user'
      );

      // Remove from list
      setSuggestions((prev) => prev.filter((s) => s.id !== suggestion.id));
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to reject suggestion');
    }
  };

  const executeSuggestion = async (suggestion: MCPSuggestion) => {
    setSelectedSuggestion(suggestion);
    setConfirmationText('');
    setShowExecutionDialog(true);
  };

  const confirmExecution = async () => {
    if (!selectedSuggestion?.approval_id) return;

    // Validate confirmation text for high-risk operations
    if (selectedSuggestion.risk_level === 'critical') {
      if (confirmationText !== 'I UNDERSTAND THE RISKS') {
        setError('Please type the confirmation text exactly');
        return;
      }
    } else if (selectedSuggestion.risk_level === 'high') {
      if (confirmationText.toUpperCase() !== 'EXECUTE') {
        setError('Please type EXECUTE to confirm');
        return;
      }
    }

    try {
      const result = await mcpApi.execute(
        dataSourceId,
        selectedSuggestion.approval_id,
        'user'
      );

      // Update suggestion status
      setSuggestions((prev) =>
        prev.map((s) =>
          s.id === selectedSuggestion.id ? { ...s, status: 'executed' } : s
        )
      );

      setShowExecutionDialog(false);
      setSelectedSuggestion(null);
      setConfirmationText('');
      setError(null);

      alert(`✅ Execution successful!\n\n${result.message}`);
    } catch (err: any) {
      setError(err.message || 'Execution failed');
    }
  };

  return (
    <div style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '600' }}>
          🤖 MCP Suggestions
        </h2>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)' }}>
          AI-powered database optimization suggestions from Google's Model Context Protocol
        </p>
      </div>

      {/* Request Button */}
      <div style={{ marginBottom: '20px' }}>
        <button
          onClick={requestSuggestions}
          disabled={loading}
          style={{
            padding: '10px 20px',
            fontSize: '14px',
            fontWeight: '600',
            backgroundColor: 'var(--primary)',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? '⏳ Requesting MCP Suggestions...' : '🚀 Request MCP Suggestions'}
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div
          style={{
            padding: '12px',
            marginBottom: '16px',
            backgroundColor: 'var(--error-bg)',
            color: 'var(--error)',
            borderRadius: '6px',
            fontSize: '13px',
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {/* Demo-mode banner: MCP not configured */}
      {demoMode && suggestions.length > 0 && (
        <div
          style={{
            padding: '12px',
            marginBottom: '16px',
            backgroundColor: '#fef3c7',
            color: '#92400e',
            border: '1px solid #fde68a',
            borderRadius: '6px',
            fontSize: '13px',
          }}
        >
          🧪 <strong>Demo mode</strong> — MCP is not configured, so these are illustrative
          sample suggestions. Set <code>MCP_ENABLED=true</code> and configure the MCP bridge
          (PostgreSQL only) to get real recommendations. See <code>MCP_SETUP_GUIDE.md</code>.
        </div>
      )}

      {/* Suggestions List */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {suggestions.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-secondary)' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🤖</div>
            <p style={{ fontSize: '14px' }}>No MCP suggestions yet</p>
            <p style={{ fontSize: '13px', marginTop: '8px' }}>
              Click "Request MCP Suggestions" to get AI-powered optimization recommendations
            </p>
          </div>
        )}

        {suggestions.map((suggestion) => (
          <SuggestionCard
            key={suggestion.id}
            suggestion={suggestion}
            onApprove={() => approveSuggestion(suggestion)}
            onReject={(reason) => rejectSuggestion(suggestion, reason)}
            onExecute={() => executeSuggestion(suggestion)}
          />
        ))}
      </div>

      {/* Approval Dialog */}
      {showApprovalDialog && selectedSuggestion && (
        <ApprovalDialog
          suggestion={selectedSuggestion}
          onConfirm={confirmApproval}
          onCancel={() => {
            setShowApprovalDialog(false);
            setSelectedSuggestion(null);
          }}
        />
      )}

      {/* Execution Dialog */}
      {showExecutionDialog && selectedSuggestion && (
        <ExecutionDialog
          suggestion={selectedSuggestion}
          confirmationText={confirmationText}
          onConfirmationTextChange={setConfirmationText}
          onConfirm={confirmExecution}
          onCancel={() => {
            setShowExecutionDialog(false);
            setSelectedSuggestion(null);
            setConfirmationText('');
          }}
        />
      )}
    </div>
  );
}

// Suggestion Card Component
function SuggestionCard({
  suggestion,
  onApprove,
  onReject,
  onExecute,
}: {
  suggestion: MCPSuggestion;
  onApprove: () => void;
  onReject: (reason: string) => void;
  onExecute: () => void;
}) {
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const riskColor = RISK_COLORS[suggestion.risk_level];
  const riskIcon = RISK_ICONS[suggestion.risk_level];

  return (
    <div
      style={{
        marginBottom: '16px',
        padding: '16px',
        backgroundColor: 'var(--bg-secondary)',
        borderRadius: '8px',
        borderLeft: `4px solid ${riskColor}`,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ fontSize: '16px' }}>{riskIcon}</span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: '600',
                textTransform: 'uppercase',
                color: riskColor,
              }}
            >
              {suggestion.risk_level} RISK
            </span>
          </div>
          <div style={{ fontSize: '14px', fontWeight: '600', marginBottom: '4px' }}>
            {suggestion.description}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Tool: {suggestion.mcp_tool}
          </div>
        </div>
      </div>

      {/* SQL Code */}
      <div style={{ marginBottom: '12px' }}>
        <div style={{ fontSize: '11px', fontWeight: '600', marginBottom: '6px', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
          SQL:
        </div>
        <pre
          style={{
            fontSize: '12px',
            backgroundColor: '#1e1e1e',
            color: '#d4d4d4',
            padding: '12px',
            borderRadius: '6px',
            overflow: 'auto',
            margin: 0,
          }}
        >
          {suggestion.sql}
        </pre>
      </div>

      {/* Rationale */}
      {suggestion.rationale && (
        <div style={{ marginBottom: '12px', fontSize: '13px', color: 'var(--text-secondary)' }}>
          <strong>Why:</strong> {suggestion.rationale}
        </div>
      )}

      {/* Warnings */}
      {suggestion.warnings.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '11px', fontWeight: '600', marginBottom: '6px', color: '#f59e0b' }}>
            ⚠️ WARNINGS:
          </div>
          {suggestion.warnings.map((warning, idx) => (
            <div key={idx} style={{ fontSize: '12px', color: '#f59e0b', marginBottom: '4px' }}>
              • {warning}
            </div>
          ))}
        </div>
      )}

      {/* Recommendation */}
      <div
        style={{
          padding: '12px',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          borderRadius: '6px',
          marginBottom: '12px',
          fontSize: '13px',
        }}
      >
        {suggestion.recommendation}
      </div>

      {/* Impact Details */}
      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
        <strong>Impact:</strong> Tables: {suggestion.tables_affected.join(', ') || 'None'} •
        Reversible: {suggestion.is_reversible ? 'Yes' : 'No'} •
        Backup required: {suggestion.requires_backup ? 'Yes' : 'No'}
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: '8px' }}>
        {suggestion.status === 'pending_approval' && (
          <>
            <button
              onClick={onApprove}
              style={{
                flex: 1,
                padding: '8px 16px',
                fontSize: '13px',
                fontWeight: '600',
                backgroundColor: '#10b981',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              ✓ Approve
            </button>
            <button
              onClick={() => setShowRejectDialog(true)}
              style={{
                flex: 1,
                padding: '8px 16px',
                fontSize: '13px',
                fontWeight: '600',
                backgroundColor: 'var(--error)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              ✗ Reject
            </button>
          </>
        )}

        {suggestion.status === 'approved' && (
          <button
            onClick={onExecute}
            style={{
              flex: 1,
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: '600',
              backgroundColor: 'var(--primary)',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            ▶ Execute
          </button>
        )}

        {suggestion.status === 'executed' && (
          <div style={{ padding: '8px', fontSize: '13px', color: '#10b981', fontWeight: '600' }}>
            ✅ Executed Successfully
          </div>
        )}
      </div>

      {/* Reject Dialog */}
      {showRejectDialog && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setShowRejectDialog(false)}
        >
          <div
            style={{
              backgroundColor: 'white',
              padding: '24px',
              borderRadius: '8px',
              maxWidth: '400px',
              width: '90%',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: '600' }}>
              Reject Suggestion
            </h3>
            <p style={{ margin: '0 0 16px 0', fontSize: '13px', color: 'var(--text-secondary)' }}>
              Please provide a reason for rejecting this suggestion:
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter rejection reason..."
              style={{
                width: '100%',
                minHeight: '80px',
                padding: '8px',
                fontSize: '13px',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                marginBottom: '16px',
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => setShowRejectDialog(false)}
                style={{
                  flex: 1,
                  padding: '8px',
                  fontSize: '13px',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (rejectReason.trim()) {
                    onReject(rejectReason);
                    setShowRejectDialog(false);
                    setRejectReason('');
                  }
                }}
                disabled={!rejectReason.trim()}
                style={{
                  flex: 1,
                  padding: '8px',
                  fontSize: '13px',
                  backgroundColor: 'var(--error)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: rejectReason.trim() ? 'pointer' : 'not-allowed',
                  opacity: rejectReason.trim() ? 1 : 0.5,
                }}
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Approval Dialog Component
function ApprovalDialog({
  onConfirm,
  onCancel,
}: {
  suggestion: MCPSuggestion;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          backgroundColor: 'white',
          padding: '24px',
          borderRadius: '8px',
          maxWidth: '500px',
          width: '90%',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
          Approve Suggestion?
        </h3>
        <p style={{ margin: '0 0 16px 0', fontSize: '14px' }}>
          You are about to approve this optimization suggestion. This will unlock the Execute button.
        </p>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1,
              padding: '10px',
              fontSize: '14px',
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            style={{
              flex: 1,
              padding: '10px',
              fontSize: '14px',
              fontWeight: '600',
              backgroundColor: '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            ✓ Approve
          </button>
        </div>
      </div>
    </div>
  );
}

// Execution Dialog Component
function ExecutionDialog({
  suggestion,
  confirmationText,
  onConfirmationTextChange,
  onConfirm,
  onCancel,
}: {
  suggestion: MCPSuggestion;
  confirmationText: string;
  onConfirmationTextChange: (text: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const needsConfirmation = suggestion.risk_level === 'high' || suggestion.risk_level === 'critical';

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          backgroundColor: 'white',
          padding: '24px',
          borderRadius: '8px',
          maxWidth: '600px',
          width: '90%',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600', color: suggestion.risk_level === 'critical' ? '#991b1b' : 'inherit' }}>
          {suggestion.risk_level === 'critical' ? '🚨 CRITICAL OPERATION' : '⚠️ Execute Suggestion?'}
        </h3>

        <p style={{ margin: '0 0 16px 0', fontSize: '14px' }}>
          You are about to execute the following SQL:
        </p>

        <pre
          style={{
            fontSize: '12px',
            backgroundColor: '#1e1e1e',
            color: '#d4d4d4',
            padding: '12px',
            borderRadius: '6px',
            overflow: 'auto',
            marginBottom: '16px',
          }}
        >
          {suggestion.sql}
        </pre>

        {suggestion.warnings.length > 0 && (
          <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: '#fef3c7', borderRadius: '6px' }}>
            <div style={{ fontSize: '12px', fontWeight: '600', marginBottom: '8px' }}>⚠️ Warnings:</div>
            {suggestion.warnings.map((warning, idx) => (
              <div key={idx} style={{ fontSize: '12px', marginBottom: '4px' }}>
                • {warning}
              </div>
            ))}
          </div>
        )}

        {needsConfirmation && (
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '8px' }}>
              Type "{suggestion.risk_level === 'critical' ? 'I UNDERSTAND THE RISKS' : 'EXECUTE'}" to confirm:
            </label>
            <input
              type="text"
              value={confirmationText}
              onChange={(e) => onConfirmationTextChange(e.target.value)}
              placeholder={suggestion.risk_level === 'critical' ? 'I UNDERSTAND THE RISKS' : 'EXECUTE'}
              style={{
                width: '100%',
                padding: '8px',
                fontSize: '13px',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
              }}
            />
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1,
              padding: '10px',
              fontSize: '14px',
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            style={{
              flex: 1,
              padding: '10px',
              fontSize: '14px',
              fontWeight: '600',
              backgroundColor: suggestion.risk_level === 'critical' ? '#991b1b' : 'var(--primary)',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            ▶ Execute
          </button>
        </div>
      </div>
    </div>
  );
}
