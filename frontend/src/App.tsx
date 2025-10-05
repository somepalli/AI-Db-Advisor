import { useState } from 'react';
import './App.css';
import { ConnectionPanel } from './components/ConnectionPanel';
import { DBExplorer } from './components/DBExplorer';
import { SQLAssistant } from './components/SQLAssistant';

function App() {
  const [selectedDataSource, setSelectedDataSource] = useState<string | null>(null);

  const handleSelectDataSource = (dsId: string) => {
    setSelectedDataSource(dsId);
  };

  return (
    <div className="app">
      <div className="three-panel-layout">
        {/* Panel 1: Connection Management */}
        <div className="panel panel-sidebar" style={{ flex: '0 0 280px' }}>
          <div className="panel-header">
            <h2>🔌 Control Panel</h2>
          </div>
          <div className="panel-content">
            <ConnectionPanel
              onSelectDataSource={handleSelectDataSource}
              selectedDataSource={selectedDataSource}
            />
          </div>
        </div>

        {/* Panel 2: Database Explorer */}
        <div className="panel panel-sidebar" style={{ flex: '0 0 300px' }}>
          <div className="panel-header">
            <h2>🗂️ Explorer</h2>
          </div>
          <div className="panel-content">
            {selectedDataSource ? (
              <DBExplorer dataSourceId={selectedDataSource} />
            ) : (
              <div style={{ padding: '16px', color: 'var(--text-secondary)', fontSize: '14px' }}>
                Select a connection to view database structure
              </div>
            )}
          </div>
        </div>

        {/* Panel 3: SQL Assistant (Full Width) */}
        <div className="panel panel-main" style={{ flex: 1 }}>
          {selectedDataSource ? (
            <SQLAssistant dataSourceId={selectedDataSource} />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                <div style={{ fontSize: '64px', marginBottom: '16px' }}>🤖</div>
                <h2 style={{ fontSize: '24px', fontWeight: '600', marginBottom: '8px' }}>AI SQL Assistant</h2>
                <p style={{ fontSize: '14px' }}>Select a connection to start building queries with AI assistance</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
