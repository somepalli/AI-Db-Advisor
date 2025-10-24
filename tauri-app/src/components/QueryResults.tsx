import { useState } from 'react';

interface Props {
  columns: string[];
  rows: Record<string, any>[];
  loading?: boolean;
}

export function QueryResults({ columns, rows, loading }: Props) {
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 100;

  const totalPages = Math.ceil(rows.length / rowsPerPage);
  const startIndex = (currentPage - 1) * rowsPerPage;
  const endIndex = startIndex + rowsPerPage;
  const displayRows = rows.slice(startIndex, endIndex);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
        <p>Executing query...</p>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>📊</div>
        <p>No results found</p>
      </div>
    );
  }

  return (
    <div>
      {/* Results Header */}
      <div style={{ padding: '12px', backgroundColor: '#3a3a3a', borderBottom: '1px solid #4a4a4a' }}>
        <span style={{ fontSize: '13px', fontWeight: '600', color: '#e0e0e0' }}>
          {rows.length} rows returned
        </span>
        {totalPages > 1 && (
          <span style={{ fontSize: '12px', color: '#a0a0a0', marginLeft: '12px' }}>
            Page {currentPage} of {totalPages}
          </span>
        )}
      </div>

      {/* Results Table */}
      <div style={{ overflowX: 'auto', maxHeight: '400px', overflowY: 'auto', backgroundColor: '#2d2d2d' }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '13px',
        }}>
          <thead style={{
            position: 'sticky',
            top: 0,
            backgroundColor: '#3a3a3a',
            borderBottom: '2px solid #4a4a4a',
          }}>
            <tr>
              <th style={{
                padding: '8px 12px',
                textAlign: 'left',
                fontWeight: '600',
                color: '#a0a0a0',
                backgroundColor: '#3a3a3a',
                fontSize: '11px',
                textTransform: 'uppercase',
              }}>
                #
              </th>
              {columns.map((col) => (
                <th
                  key={col}
                  style={{
                    padding: '8px 12px',
                    textAlign: 'left',
                    fontWeight: '600',
                    color: '#a0a0a0',
                    backgroundColor: '#3a3a3a',
                    fontSize: '11px',
                    textTransform: 'uppercase',
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                style={{
                  borderBottom: '1px solid #3a3a3a',
                  backgroundColor: rowIdx % 2 === 0 ? '#2d2d2d' : '#353535',
                }}
              >
                <td style={{
                  padding: '8px 12px',
                  color: '#a0a0a0',
                  fontSize: '11px',
                }}>
                  {startIndex + rowIdx + 1}
                </td>
                {columns.map((col) => (
                  <td
                    key={col}
                    style={{
                      padding: '8px 12px',
                      maxWidth: '300px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      color: '#e0e0e0',
                    }}
                  >
                    {row[col] === null ? (
                      <span style={{ color: '#888888', fontStyle: 'italic' }}>NULL</span>
                    ) : (
                      String(row[col])
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '8px',
          padding: '12px',
          borderTop: '1px solid #4a4a4a',
          backgroundColor: '#2d2d2d',
        }}>
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              backgroundColor: currentPage === 1 ? '#3a3a3a' : 'var(--primary)',
              color: currentPage === 1 ? '#666666' : 'white',
              border: currentPage === 1 ? '1px solid #4a4a4a' : 'none',
              borderRadius: '4px',
              cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
            }}
          >
            Previous
          </button>
          <span style={{ padding: '6px 12px', fontSize: '12px', color: '#a0a0a0' }}>
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              backgroundColor: currentPage === totalPages ? '#3a3a3a' : 'var(--primary)',
              color: currentPage === totalPages ? '#666666' : 'white',
              border: currentPage === totalPages ? '1px solid #4a4a4a' : 'none',
              borderRadius: '4px',
              cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
