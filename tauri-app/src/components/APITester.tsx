import { useState } from 'react';
import { healthApi, datasourcesApi, analyzeApi } from '../api/client';

interface TestResult {
  endpoint: string;
  status: 'pending' | 'success' | 'error';
  message?: string;
  data?: any;
}

export function APITester() {
  const [results, setResults] = useState<TestResult[]>([]);
  const [testing, setTesting] = useState(false);
  const [testDsId, setTestDsId] = useState('tauri-db');
  const [testSql, setTestSql] = useState('SELECT * FROM users LIMIT 10');

  const updateResult = (endpoint: string, status: TestResult['status'], message?: string, data?: any) => {
    setResults(prev => {
      const existing = prev.find(r => r.endpoint === endpoint);
      if (existing) {
        return prev.map(r => r.endpoint === endpoint ? { endpoint, status, message, data } : r);
      }
      return [...prev, { endpoint, status, message, data }];
    });
  };

  const testEndpoint = async (name: string, endpoint: string, fn: () => Promise<any>) => {
    updateResult(endpoint, 'pending');
    try {
      const data = await fn();
      updateResult(endpoint, 'success', 'OK', data);
    } catch (error) {
      updateResult(endpoint, 'error', (error as Error).message);
    }
  };

  const runAllTests = async () => {
    setTesting(true);
    setResults([]);

    // Health & Root
    await testEndpoint('Health Check', 'GET /healthz', () => healthApi.healthz());
    await testEndpoint('Root', 'GET /', () => healthApi.root());

    // Datasources
    await testEndpoint('List Datasources', 'GET /datasources', () => datasourcesApi.list());

    // Note: POST endpoints require data, so we'll test them conditionally
    // You can uncomment these after creating a test datasource

    // Analyze endpoints (these require a valid datasource)
    await testEndpoint('Get Schema', `GET /analyze/${testDsId}/schema`, () =>
      analyzeApi.getSchema(testDsId));

    await testEndpoint('Top Queries', `GET /analyze/${testDsId}/top`, () =>
      analyzeApi.getTopQueries(testDsId, 5));

    await testEndpoint('Get Locks', `GET /analyze/${testDsId}/locks`, () =>
      analyzeApi.getLocks(testDsId));

    await testEndpoint('Get Stats', `GET /analyze/${testDsId}/stats`, () =>
      analyzeApi.getStats(testDsId));

    // POST endpoints with test data
    await testEndpoint('Explain', `POST /analyze/${testDsId}/explain`, () =>
      analyzeApi.explain(testDsId, testSql, false));

    await testEndpoint('Advise Index', `POST /analyze/${testDsId}/advise/index`, () =>
      analyzeApi.adviseIndex(testDsId, testSql));

    await testEndpoint('Advise Rewrite', `POST /analyze/${testDsId}/advise/rewrite`, () =>
      analyzeApi.adviseRewrite(testDsId, testSql));

    await testEndpoint('Advise AI', `POST /analyze/${testDsId}/advise/ai`, () =>
      analyzeApi.adviseAI(testDsId, testSql));

    await testEndpoint('Explain Plan AI', `POST /analyze/${testDsId}/explain/ai`, () =>
      analyzeApi.explainPlanAI(testDsId, testSql, false));

    await testEndpoint('Hypo Index', `POST /analyze/${testDsId}/hypo-index`, () =>
      analyzeApi.hypoIndex(testDsId, { sql: testSql, indexes: [] }));

    setTesting(false);
  };

  const getStatusColor = (status: TestResult['status']) => {
    switch (status) {
      case 'success': return '#10b981';
      case 'error': return '#ef4444';
      case 'pending': return '#f59e0b';
      default: return '#6b7280';
    }
  };

  const getStatusIcon = (status: TestResult['status']) => {
    switch (status) {
      case 'success': return '✓';
      case 'error': return '✗';
      case 'pending': return '⋯';
      default: return '○';
    }
  };

  return (
    <div>
      <div className="page-header">
        <h2>API Connectivity Tester</h2>
        <p>Test all backend API endpoints</p>
      </div>

      <div className="card" style={{ marginBottom: '20px' }}>
        <h3>Test Configuration</h3>
        <div className="form-group">
          <label>Test Datasource ID</label>
          <input
            type="text"
            value={testDsId}
            onChange={(e) => setTestDsId(e.target.value)}
            placeholder="test-db"
          />
          <small>Enter a valid datasource ID to test analyze endpoints</small>
        </div>
        <div className="form-group">
          <label>Test SQL Query</label>
          <textarea
            value={testSql}
            onChange={(e) => setTestSql(e.target.value)}
            placeholder="SELECT * FROM users LIMIT 10"
            rows={3}
          />
        </div>
        <button
          className="btn btn-primary"
          onClick={runAllTests}
          disabled={testing}
        >
          {testing ? 'Testing...' : 'Run All Tests'}
        </button>
      </div>

      <div className="card">
        <h3>Test Results ({results.filter(r => r.status === 'success').length}/{results.length})</h3>

        {results.length === 0 && (
          <div className="empty-state">
            <p>Click "Run All Tests" to start testing API endpoints</p>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {results.map((result, idx) => (
            <div
              key={idx}
              style={{
                padding: '12px',
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: '6px',
                borderLeft: `4px solid ${getStatusColor(result.status)}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{ fontSize: '18px', color: getStatusColor(result.status) }}>
                  {getStatusIcon(result.status)}
                </span>
                <code style={{ fontWeight: 500 }}>{result.endpoint}</code>
              </div>
              {result.message && (
                <div style={{
                  fontSize: '12px',
                  color: result.status === 'error' ? '#ef4444' : '#6b7280',
                  marginLeft: '26px'
                }}>
                  {result.message}
                </div>
              )}
              {result.data && result.status === 'success' && (
                <details style={{ marginLeft: '26px', marginTop: '8px' }}>
                  <summary style={{ cursor: 'pointer', fontSize: '12px', color: '#6b7280' }}>
                    View Response
                  </summary>
                  <pre style={{
                    fontSize: '11px',
                    backgroundColor: '#1e293b',
                    padding: '8px',
                    borderRadius: '4px',
                    marginTop: '8px',
                    overflow: 'auto',
                    maxHeight: '200px'
                  }}>
                    {JSON.stringify(result.data, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
