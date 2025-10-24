/**
 * Chat History Dropdown - Cursor-like chat session history
 *
 * Features:
 * - List all chat sessions with titles
 * - Create new session
 * - Switch between sessions
 * - Delete sessions
 * - Session metadata (date, message count)
 */
import { useState, useEffect, useRef } from 'react';
import { chatHistoryApi } from '../api/client';

interface ChatSession {
  session_id: string;
  title: string;
  message_count: number;
  last_message_time: string;
  first_message: string;
}

interface Props {
  dataSourceId: string;
  currentSessionId: string;
  onSessionChange: (sessionId: string) => void;
  onNewSession: () => void;
}

export function ChatHistoryDropdown({ dataSourceId, currentSessionId, onSessionChange, onNewSession }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [hoveredSession, setHoveredSession] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Close dropdown when clicking outside
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadSessions();
    }
  }, [isOpen, dataSourceId]);

  const loadSessions = async () => {
    setLoading(true);
    try {
      // Get all messages for this data source
      const response = await chatHistoryApi.getHistory(dataSourceId, undefined, 1000);

      // Group messages by session_id and create session metadata
      const sessionMap = new Map<string, ChatSession>();

      response.messages.forEach((msg) => {
        if (!sessionMap.has(msg.session_id)) {
          sessionMap.set(msg.session_id, {
            session_id: msg.session_id,
            title: '', // Will be set below
            message_count: 0,
            last_message_time: msg.timestamp,
            first_message: msg.content,
          });
        }

        const session = sessionMap.get(msg.session_id)!;
        session.message_count++;

        // Update last message time if this message is newer
        if (new Date(msg.timestamp) > new Date(session.last_message_time)) {
          session.last_message_time = msg.timestamp;
        }

        // Keep the first user message as the title source
        if (msg.role === 'user' && !session.title) {
          session.title = msg.content.slice(0, 50) + (msg.content.length > 50 ? '...' : '');
        }
      });

      // Convert map to array and sort by last message time (newest first)
      const sessionList = Array.from(sessionMap.values())
        .sort((a, b) => new Date(b.last_message_time).getTime() - new Date(a.last_message_time).getTime())
        .map((session) => ({
          ...session,
          title: session.title || 'New Chat',
        }));

      setSessions(sessionList);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent session selection

    if (!confirm('Delete this chat session?')) return;

    try {
      await chatHistoryApi.deleteSession(dataSourceId, sessionId);

      // Remove from list
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));

      // If deleting current session, create new one
      if (sessionId === currentSessionId) {
        onNewSession();
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const formatTimestamp = (timestamp: string): string => {
    // Parse UTC timestamp from backend and convert to local time
    const date = new Date(timestamp);

    // Check if timestamp is valid
    if (isNaN(date.getTime())) {
      return 'Unknown';
    }

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    // For older messages, show local date
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    });
  };

  const currentSession = sessions.find(s => s.session_id === currentSessionId);

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      {/* History Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          fontSize: '13px',
          backgroundColor: isOpen ? 'var(--bg-secondary)' : 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-color)',
          borderRadius: '6px',
          cursor: 'pointer',
          transition: 'all 0.2s',
        }}
        onMouseEnter={(e) => {
          if (!isOpen) {
            e.currentTarget.style.backgroundColor = 'var(--bg-secondary)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isOpen) {
            e.currentTarget.style.backgroundColor = 'transparent';
          }
        }}
      >
        <span style={{ fontSize: '16px' }}>💬</span>
        <span style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {currentSession?.title || 'New Chat'}
        </span>
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          {isOpen ? '▲' : '▼'}
        </span>
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            width: '320px',
            maxHeight: '400px',
            backgroundColor: 'white',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Header */}
          <div style={{ padding: '12px', borderBottom: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4 style={{ margin: 0, fontSize: '14px', fontWeight: '600' }}>Chat History</h4>
              <button
                onClick={() => {
                  onNewSession();
                  setIsOpen(false);
                }}
                style={{
                  padding: '4px 10px',
                  fontSize: '12px',
                  backgroundColor: 'var(--primary)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span>+</span>
                <span>New Chat</span>
              </button>
            </div>
          </div>

          {/* Sessions List */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                Loading sessions...
              </div>
            ) : sessions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                <p style={{ fontSize: '13px' }}>No chat history yet</p>
                <p style={{ fontSize: '12px', marginTop: '8px' }}>Start a conversation to create your first session</p>
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.session_id}
                  onClick={() => {
                    onSessionChange(session.session_id);
                    setIsOpen(false);
                  }}
                  onMouseEnter={() => setHoveredSession(session.session_id)}
                  onMouseLeave={() => setHoveredSession(null)}
                  style={{
                    padding: '10px',
                    marginBottom: '4px',
                    backgroundColor:
                      session.session_id === currentSessionId
                        ? '#e3f2fd'
                        : hoveredSession === session.session_id
                        ? 'var(--bg-secondary)'
                        : 'transparent',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    transition: 'background-color 0.2s',
                    position: 'relative',
                    borderLeft: session.session_id === currentSessionId ? '3px solid var(--primary)' : 'none',
                    paddingLeft: session.session_id === currentSessionId ? '7px' : '10px',
                  }}
                >
                  {/* Session Title */}
                  <div
                    style={{
                      fontSize: '13px',
                      fontWeight: session.session_id === currentSessionId ? '600' : '400',
                      marginBottom: '4px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      paddingRight: '24px', // Space for delete button
                    }}
                  >
                    {session.title}
                  </div>

                  {/* Metadata */}
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', gap: '8px' }}>
                    <span>{session.message_count} messages</span>
                    <span>•</span>
                    <span>{formatTimestamp(session.last_message_time)}</span>
                  </div>

                  {/* Delete Button (shown on hover) */}
                  {hoveredSession === session.session_id && (
                    <button
                      onClick={(e) => handleDeleteSession(session.session_id, e)}
                      style={{
                        position: 'absolute',
                        top: '10px',
                        right: '10px',
                        width: '20px',
                        height: '20px',
                        padding: 0,
                        fontSize: '12px',
                        backgroundColor: 'var(--error)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      🗑️
                    </button>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          {sessions.length > 0 && (
            <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border-color)', fontSize: '11px', color: 'var(--text-secondary)', textAlign: 'center' }}>
              {sessions.length} session{sessions.length !== 1 ? 's' : ''}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
