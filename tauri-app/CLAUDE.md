# CLAUDE.md - Tauri Frontend

This file provides guidance to Claude Code when working with the Tauri desktop application frontend.

## Overview

This is a **Tauri v2** desktop application that provides a modern UI for the AI DB Advisor backend. It replaces the FastUI web interface with a native desktop experience.

**Supported Databases (8 types):**
- **SQL Databases**: PostgreSQL, MySQL/MariaDB, SQL Server, Oracle, SQLite
- **NoSQL Databases**: MongoDB (document), Redis (key-value), Cassandra (wide-column)

**Tech Stack**:
- **Tauri v2**: Rust-based desktop framework (alternative to Electron)
- **React 18**: UI framework with hooks
- **TypeScript 5**: Type-safe development
- **Vite 6**: Lightning-fast build tool
- **CSS-in-JS**: Inline styles for component styling

## Project Structure

```
tauri-app/
├── src/                    # React application source
│   ├── components/         # React components
│   │   ├── ConnectionPanel.tsx          # Database connection management
│   │   ├── DBExplorer.tsx              # Schema browser
│   │   ├── SQLEditor.tsx               # Basic SQL editor
│   │   ├── SQLEditorWithAutocomplete.tsx  # Main SQL editor (ACTIVE)
│   │   ├── QueryAnalyzer.tsx           # AI suggestions panel
│   │   └── Dashboard.tsx               # Performance stats (unused)
│   ├── api/
│   │   └── client.ts       # HTTP API client
│   ├── types/
│   │   └── index.ts        # TypeScript type definitions
│   ├── App.tsx             # Root component (4-panel layout)
│   ├── main.tsx            # Application entry point
│   ├── App.css             # Global styles
│   └── index.css           # Base styles
│
├── src-tauri/              # Tauri Rust backend
│   ├── src/
│   │   └── lib.rs          # Tauri commands
│   ├── icons/              # App icons
│   ├── Cargo.toml          # Rust dependencies
│   └── tauri.conf.json     # Tauri configuration
│
├── public/                 # Static assets
├── package.json            # Node dependencies
├── tsconfig.json           # TypeScript config
├── vite.config.ts          # Vite configuration
└── CLAUDE.md              # This file
```

## Application Architecture

### 4-Panel Desktop Layout (App.tsx)

```
┌────────────────────────────────────────────────────────────────────────┐
│                         AI DB Advisor Desktop                           │
├─────────────┬──────────────┬──────────────┬───────────────────────────┤
│             │              │              │                           │
│ Connection  │ DB Explorer  │  SQL Editor  │    AI Suggestions         │
│   Panel     │              │              │        Panel              │
│             │              │              │                           │
│ • Add DB    │ • Tables     │ • Query      │ 🤖 AI Suggestions        │
│ • Remove DB │ • Columns    │ • Execute    │ ✏️ Rewrite Advice         │
│ • Select    │ • Types      │ • Clear      │ 📊 Index Advice           │
│   Active    │ • Nullable   │ • Copy to AI │ 📈 Explain Plan           │
│             │              │              │                           │
└─────────────┴──────────────┴──────────────┴───────────────────────────┘
```

### Component Hierarchy

```
App (main.tsx)
└── App.tsx (4 panels)
    ├── ConnectionPanel
    │   └── Datasource management
    ├── DBExplorer
    │   └── Schema tree view
    ├── SQLEditorWithAutocomplete (ACTIVE)
    │   ├── Textarea with autocomplete
    │   ├── Execute/Clear/Copy buttons
    │   ├── AI Suggestions section
    │   ├── Rewrite Advice section
    │   ├── Index Advice section
    │   └── Explain Plan section
    └── QueryAnalyzer
        └── Placeholder for AI panel
```

## Key Components

### 1. ConnectionPanel.tsx

**Purpose**: Manage multi-database connections (8 database types)

**Features**:
- Add new connection (ID, Engine, DSN)
- List all connections
- Select active connection
- Delete connection (trash icon button)
- Connection status indicator
- Dynamic DSN placeholder based on engine type
- Tabbed interface: Connections, Stats, Locks, Queries

**Engine Selection**:
Dropdown with organized optgroups:
- **SQL Databases**: PostgreSQL, MySQL/MariaDB, SQL Server, Oracle
- **NoSQL Databases**: MongoDB, Redis, Cassandra
- **Other**: SQLite

**State**:
```typescript
const [datasources, setDatasources] = useState<Record<string, DataSource>>({})
const [formData, setFormData] = useState({id: '', engine: 'postgres', dsn: ''})
const [error, setError] = useState<string | null>(null)
const [activeTab, setActiveTab] = useState<Tab>('connections')
```

**API Calls**:
- `datasourcesApi.list()`: Fetch all connections
- `datasourcesApi.create(data)`: Add new connection
- `datasourcesApi.delete(dsId)`: Delete connection
- `analyzeApi.getStats(dsId)`: Get database statistics
- `analyzeApi.getLocks(dsId)`: Get database locks
- `analyzeApi.getTopQueries(dsId)`: Get top queries

**DSN Formats** (Dynamic Placeholder):
```typescript
const getDSNPlaceholder = () => {
  switch (formData.engine) {
    case 'postgres': return 'postgresql://user:pass@host:5432/db'
    case 'mysql': return 'mysql://user:pass@host:3306/db'
    case 'sqlserver': return 'mssql://user:pass@host:1433/db'
    case 'oracle': return 'oracle://user:pass@host:1521/service'
    case 'mongodb': return 'mongodb://user:pass@host:27017/db'
    case 'redis': return 'redis://host:6379/0'
    case 'sqlite': return 'sqlite:///path/to/database.db'
    case 'cassandra': return 'cassandra://host:9042/keyspace'
  }
}
```

### 2. DBExplorer.tsx

**Purpose**: Browse database schema and optimize tables/database

**Features**:
- Fetches schema on connection select (works for all DB types)
- Displays tables/collections in collapsible list
- Shows column/field details:
  - Column name
  - Data type
  - Nullable (YES/NO)
- Loading and error states

**Optimization Features**:
- **🚀 Optimize DB** button: Database-level AI optimizations
- **⚡ Optimize** button per table: Table-level AI optimizations
- Checkbox selection for suggestions
- **✅ Apply Selected** button: Batch apply optimizations
- Apply results display with success/error counts

**API Calls**:
- `analyzeApi.getSchema(dataSourceId)`: Fetch schema
- `optimizationApi.optimizeDatabase(dsId)`: Get DB-level suggestions
- `optimizationApi.optimizeTable(dsId, tableName)`: Get table-level suggestions
- `optimizationApi.applyOptimizations(dsId, sqlStatements)`: Apply selected suggestions

**Schema Structure** (Unified across all DB types):
```typescript
{
  tables: {
    // SQL databases: schema.table format
    "public.students": [
      {column: "student_id", type: "integer", nullable: "NO"},
      {column: "first_name", type: "character varying", nullable: "YES"},
      ...
    ],
    // NoSQL databases: database.collection or key patterns
    "mydb.users": [
      {column: "_id", type: "ObjectId", nullable: "NO"},
      {column: "username", type: "string", nullable: "YES"},
      ...
    ],
    ...
  }
}
```

### 3. SQLEditorWithAutocomplete.tsx (Main Editor)

**Purpose**: Execute SQL queries with autocomplete and display all analysis results

**Features**:

#### Input & Autocomplete
- Multi-line SQL textarea
- Real-time autocomplete:
  - **Tables**: From schema
  - **Columns**: From all tables
  - **Keywords**: SELECT, FROM, WHERE, JOIN, etc.
- Keyboard navigation:
  - Arrow Up/Down: Navigate suggestions
  - Enter: Insert selected item
  - Escape: Close autocomplete
- Syntax validation:
  - Unclosed quotes detection
  - Unknown table warnings
  - Visual error indicators (red dotted border)

#### Execution
When user clicks "▶ Execute":
1. Clears previous results
2. Shows loading with section name: "⏳ AI Suggestions..."
3. Calls 4 API endpoints **sequentially**:
   - `adviseAI()` → AI Suggestions
   - `adviseRewrite()` → Rewrite Advice
   - `adviseIndex()` → Index Advice
   - `explain()` → Explain Plan
4. Updates UI as each section completes

#### Display Sections (in order)

**🤖 AI Suggestions** (displayed first):
- Shows ONLY AI-related suggestions
- Each suggestion card shows:
  - Type badge (index/rewrite/note)
  - Summary (bold)
  - Rationale (gray text)
  - SQL code (for rewrites/indexes)
  - Expected gain (green text)
- Color: Primary blue

**✏️ Rewrite Advice** (second):
- Query optimization recommendations
- Shows:
  - Category
  - Summary
  - SQL fix
  - Expected gain (green)
  - Risk (red if present)
- Color: Orange (#f59e0b)

**📊 Index Advice** (third):
- Index creation recommendations
- Shows:
  - Category
  - Summary
  - CREATE INDEX statement
  - Expected gain
- Color: Purple (#8b5cf6)

**📈 Explain Plan** (fourth):
- Full JSON execution plan
- Formatted with syntax highlighting
- Color: Cyan (#06b6d4)

#### State Management
```typescript
const [sql, setSql] = useState('')
const [loading, setLoading] = useState(false)
const [loadingSection, setLoadingSection] = useState('')
const [aiSuggestions, setAiSuggestions] = useState<AIAdviceResponse | null>(null)
const [rewriteAdvice, setRewriteAdvice] = useState<Recommendation[]>([])
const [indexAdvice, setIndexAdvice] = useState<Recommendation[]>([])
const [explainPlan, setExplainPlan] = useState<any>(null)
const [error, setError] = useState<string | null>(null)

// Autocomplete state
const [autocompleteItems, setAutocompleteItems] = useState<AutocompleteItem[]>([])
const [showAutocomplete, setShowAutocomplete] = useState(false)
const [selectedIndex, setSelectedIndex] = useState(0)
const [syntaxErrors, setSyntaxErrors] = useState([])
```

#### Copy to AI Editor Button
- Optional feature for copying queries
- Requires `onCopyToAIEditor` prop
- Disabled when no SQL entered
- Button: "📋 Copy to AI SQL Editor"

### 4. QueryAnalyzer.tsx

**Purpose**: Display AI suggestions (currently unused - integrated into SQLEditor)

**Note**: AI suggestions are now shown directly in SQLEditorWithAutocomplete, making this component redundant.

## API Client (api/client.ts)

### Base Configuration

```typescript
const API_BASE_URL = 'http://127.0.0.1:8000'
```

### API Modules

#### healthApi
```typescript
healthz(): Promise<{status: string}>
root(): Promise<{message: string, version?: string}>
```

#### datasourcesApi
```typescript
list(): Promise<Record<string, DataSource>>
create(data: DataSourceCreate): Promise<{message: string}>
```

#### analyzeApi
```typescript
getSchema(dsId: string): Promise<SchemaResponse>
getTopQueries(dsId: string, limit: number = 10): Promise<TopQuery[]>
explain(dsId: string, sql: string, analyze: boolean = false): Promise<ExplainPlan>
getLocks(dsId: string): Promise<Lock[]>
getStats(dsId: string): Promise<Stats>
adviseIndex(dsId: string, sql: string): Promise<Recommendation[]>
adviseRewrite(dsId: string, sql: string): Promise<Recommendation[]>
adviseAI(dsId: string, sql: string): Promise<AIAdviceResponse>
explainPlanAI(dsId: string, sql: string, analyze: boolean = false): Promise<AIAdviceResponse>
```

### Error Handling

All API calls use try-catch with user-friendly error messages:
```typescript
try {
  const data = await apiRequest(...)
  return data
} catch (err) {
  throw new Error(`API request failed: ${response.statusText}`)
}
```

## Type System (types/index.ts)

### Core Types

```typescript
// Data source connection
interface DataSource {
  id: string
  engine: string
  dsn: string
}

// Schema types
interface TableSchema {
  column: string
  type: string
  nullable: string
}

interface SchemaResponse {
  tables: Record<string, TableSchema[]>
}

// Query analysis
interface TopQuery {
  query: string
  calls: number
  mean_time_ms: number
  rows: number
  source: string
}

interface Lock {
  locktype: string
  mode: string
  granted: boolean
  pid: number
  age: string
}

interface Stats {
  total_db_size: number
  active_backends: number
}

// Recommendations
interface Recommendation {
  category: string
  summary: string
  sql_fix?: string
  risk?: string
  expected_gain?: string
  details?: any
}

// AI suggestions
interface AIAdviceResponse {
  suggestions: Array<{
    type: string              // "index" | "rewrite" | "note"
    summary: string
    rationale?: string
    new_sql?: string          // For rewrites
    sql_fix?: string          // For indexes
    expected_gain?: string
    validated?: boolean
    risk?: string
  }>
}
```

## Styling System

### CSS Variables (App.css)

```css
:root {
  --primary: #3b82f6;
  --bg-primary: #ffffff;
  --bg-secondary: #f3f4f6;
  --text-primary: #1f2937;
  --text-secondary: #6b7280;
  --border-color: #e5e7eb;
  --error: #ef4444;
  --error-bg: #fee2e2;
}
```

### Component Styling

All components use **inline styles** for scoped styling:

```typescript
<div style={{
  padding: '16px',
  backgroundColor: 'var(--bg-secondary)',
  borderRadius: '6px'
}}>
```

**Benefits**:
- No CSS conflicts
- Component-scoped styles
- Type-safe style props
- Easy to customize per component

### Common Patterns

**Card**:
```typescript
style={{
  padding: '12px',
  backgroundColor: 'var(--bg-secondary)',
  borderRadius: '6px',
  marginTop: '12px'
}}
```

**Button**:
```typescript
style={{
  padding: '8px 16px',
  fontSize: '14px',
  backgroundColor: 'var(--primary)',
  color: 'white',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer'
}}
```

**Error Message**:
```typescript
style={{
  padding: '12px',
  backgroundColor: 'var(--error-bg)',
  color: 'var(--error)',
  borderRadius: '6px'
}}
```

## Tauri Configuration (src-tauri/tauri.conf.json)

### Key Settings

```json
{
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devPath": "http://localhost:5173",
    "distDir": "../dist"
  },
  "tauri": {
    "allowlist": {
      "all": false,
      "http": {
        "all": true,
        "request": true,
        "scope": ["http://127.0.0.1:8000/**"]
      }
    },
    "windows": [{
      "title": "AI DB Advisor",
      "width": 1400,
      "height": 900,
      "resizable": true,
      "fullscreen": false
    }]
  }
}
```

**Important**:
- HTTP scope allows requests to backend (127.0.0.1:8000)
- Window size optimized for 4-panel layout
- Native fetch API works with Tauri permissions

## Development Workflow

### Starting Development

```bash
# Terminal 1: Start backend
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor
python run.py

# Terminal 2: Start frontend
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor\tauri-app
npm run dev
```

**Result**:
- Backend: http://127.0.0.1:8000
- Frontend: http://localhost:5173
- Opens in browser (not Tauri window)

### Starting Tauri Desktop App

```bash
# Requires Rust toolchain
npm run tauri dev
```

**Result**: Opens native desktop window

### Building for Production

```bash
# Build Tauri app
npm run tauri build

# Output: src-tauri/target/release/bundle/
# Creates installers for Windows (.msi, .exe)
```

## Common Development Tasks

### Adding a New Component

1. Create file: `src/components/NewComponent.tsx`
2. Define props interface
3. Implement component with hooks
4. Export from component
5. Import in App.tsx or parent component

Example:
```typescript
// src/components/NewComponent.tsx
interface Props {
  dataSourceId: string
  onComplete?: () => void
}

export function NewComponent({ dataSourceId, onComplete }: Props) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  // Component logic...

  return <div>{/* JSX */}</div>
}
```

### Adding a New API Endpoint

1. Add type to `types/index.ts`
2. Add method to `api/client.ts`:
```typescript
export const analyzeApi = {
  // ... existing methods
  newEndpoint: async (dsId: string, params: any): Promise<ResponseType> => {
    return apiRequest<ResponseType>(`/analyze/${dsId}/new-endpoint`, {
      method: 'POST',
      body: JSON.stringify(params)
    })
  }
}
```
3. Use in component:
```typescript
const result = await analyzeApi.newEndpoint(dataSourceId, {/* params */})
```

### Debugging

#### Browser DevTools (Vite dev mode)
1. Run `npm run dev`
2. Open http://localhost:5173
3. Open DevTools (F12)
4. Check:
   - Console for errors
   - Network for API calls
   - React DevTools for component state

#### Tauri DevTools
1. Run `npm run tauri dev`
2. Desktop window opens
3. Right-click → Inspect Element
4. Same DevTools as browser

#### Common Issues

**API Call Fails**:
- Check backend is running (http://127.0.0.1:8000/healthz)
- Check network tab for exact error
- Verify CORS settings
- Check API endpoint URL

**Component Not Updating**:
- Verify state is set correctly
- Check React key props
- Use React DevTools to inspect state
- Add console.logs to track updates

**TypeScript Errors**:
- Run `npm run type-check`
- Check types match API response
- Verify imports are correct

## Best Practices

### React Hooks
1. **Always use hooks at top level** (not in loops/conditions)
2. **Use useEffect for side effects** (API calls, subscriptions)
3. **Use useState for local state** (form inputs, UI state)
4. **Use useMemo for expensive computations** (rarely needed)
5. **Use useCallback for function memoization** (child component props)

### State Management
1. **Lift state up** if multiple components need it
2. **Keep state local** if only one component needs it
3. **Use controlled components** for forms
4. **Avoid prop drilling** - consider context for deep props

### API Calls
1. **Always handle errors** with try-catch
2. **Show loading states** during async operations
3. **Display user-friendly error messages**
4. **Avoid parallel API calls** when order matters
5. **Use async/await** for readability

### TypeScript
1. **Avoid `any` type** - use specific types
2. **Define interfaces for props** - clear component contracts
3. **Use type imports** - `import type { ... }`
4. **Enable strict mode** - catch more errors

### Performance
1. **Batch state updates** when possible
2. **Use React.memo** for expensive components
3. **Avoid inline object/array creation** in JSX
4. **Debounce user input** for autocomplete

### Code Organization
1. **One component per file**
2. **Group related files** (component + styles + tests)
3. **Use barrel exports** (index.ts files)
4. **Keep components small** (<300 lines)

## Testing

### Unit Tests (if added)
```bash
npm run test
```

### E2E Tests (if added)
```bash
npm run test:e2e
```

### Manual Testing Checklist
- [ ] Add connection (valid DSN)
- [ ] Add connection (invalid DSN) → shows error
- [ ] Select connection → schema loads
- [ ] Type in SQL editor → autocomplete appears
- [ ] Execute query → all 4 sections appear in order
- [ ] Execute invalid query → error message shown
- [ ] Clear button → resets all sections
- [ ] Copy to AI button → works (if implemented)

## Troubleshooting

### Problem: npm run dev fails

**Solution**:
```bash
rm -rf node_modules
npm install
npm run dev
```

### Problem: Tauri build fails

**Causes**:
- Rust not installed
- Missing C++ build tools

**Solution**:
```bash
# Install Rust
winget install Rustlang.Rustup

# Install Visual C++ Build Tools
winget install Microsoft.VisualStudio.2022.BuildTools

# Restart terminal
npm run tauri build
```

### Problem: API calls return CORS error

**Check**:
1. Backend allows CORS for localhost:5173
2. Tauri allowlist includes backend URL
3. Backend is running

### Problem: Autocomplete not showing

**Check**:
1. Schema loaded successfully
2. Input has focus
3. Typing triggers onChange
4. Check `showAutocomplete` state
5. Check console for errors

## Future Enhancements

- [ ] Query history/favorites
- [ ] Multi-tab SQL editor
- [ ] Export results to CSV
- [ ] Dark mode support
- [ ] Keyboard shortcuts
- [ ] Query templates
- [ ] Performance benchmarking
- [ ] Syntax highlighting for SQL
- [ ] Query result grid view
- [ ] Save/load workspace
