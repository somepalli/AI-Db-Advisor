import { useState } from 'react';

interface CodeBlock {
  language: string;
  code: string;
  startIndex: number;
  endIndex: number;
}

interface Props {
  content: string;
  role: 'user' | 'assistant';
}

/**
 * MessageRenderer - Renders chat messages with code block detection and copy functionality
 *
 * Features:
 * - Detects markdown code blocks (```sql, ```python, etc.)
 * - Adds copy button to each code block
 * - Syntax highlighting for code
 * - Preserves text formatting outside code blocks
 */
export function MessageRenderer({ content, role }: Props) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const parseCodeBlocks = (text: string): (string | CodeBlock)[] => {
    const parts: (string | CodeBlock)[] = [];
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(text)) !== null) {
      // Add text before code block
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }

      // Add code block
      parts.push({
        language: match[1] || 'code',
        code: match[2].trim(),
        startIndex: match.index,
        endIndex: match.index + match[0].length,
      });

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text after last code block
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    // If no code blocks found, return original text
    if (parts.length === 0) {
      parts.push(text);
    }

    return parts;
  };

  const copyToClipboard = async (code: string, index: number) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const parts = parseCodeBlocks(content);

  return (
    <div style={{ fontSize: '13px', lineHeight: '1.6' }}>
      {parts.map((part, idx) => {
        if (typeof part === 'string') {
          // Render text with preserved whitespace
          return (
            <div key={idx} style={{ whiteSpace: 'pre-wrap', marginBottom: '8px' }}>
              {part}
            </div>
          );
        } else {
          // Render code block with copy button
          const codeBlock = part as CodeBlock;
          return (
            <div key={idx} style={{ marginBottom: '12px', position: 'relative' }}>
              {/* Language label and copy button */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  backgroundColor: '#2d2d2d',
                  padding: '6px 12px',
                  borderTopLeftRadius: '6px',
                  borderTopRightRadius: '6px',
                  fontSize: '11px',
                  color: '#9ca3af',
                  fontWeight: '600',
                }}
              >
                <span style={{ textTransform: 'uppercase' }}>{codeBlock.language}</span>
                <button
                  onClick={() => copyToClipboard(codeBlock.code, idx)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '11px',
                    backgroundColor: copiedIndex === idx ? '#10b981' : '#4b5563',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    transition: 'background-color 0.2s',
                    fontWeight: '500',
                  }}
                  onMouseEnter={(e) => {
                    if (copiedIndex !== idx) {
                      e.currentTarget.style.backgroundColor = '#6b7280';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (copiedIndex !== idx) {
                      e.currentTarget.style.backgroundColor = '#4b5563';
                    }
                  }}
                >
                  {copiedIndex === idx ? '✓ Copied!' : '📋 Copy'}
                </button>
              </div>

              {/* Code content */}
              <pre
                style={{
                  margin: 0,
                  padding: '12px',
                  backgroundColor: '#1e1e1e',
                  color: '#d4d4d4',
                  fontSize: '12px',
                  fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                  overflow: 'auto',
                  borderBottomLeftRadius: '6px',
                  borderBottomRightRadius: '6px',
                  lineHeight: '1.5',
                }}
              >
                <code>{codeBlock.code}</code>
              </pre>
            </div>
          );
        }
      })}
    </div>
  );
}
