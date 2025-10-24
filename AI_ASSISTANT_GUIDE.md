# AI SQL Assistant - User Guide

## Overview

The AI SQL Assistant is a comprehensive enhancement to the AI DB Advisor that transforms the Query Optimizer into an intelligent conversational AI agent capable of:

1. **Natural Language Query Generation**: Convert English descriptions to executable SQL
2. **Intelligent Query Optimization**: Context-aware performance improvements
3. **Missing Table Detection & Auto-Creation**: Automatically suggest and create missing tables
4. **Real-Time Query Validation**: Identify issues before execution
5. **Integrated Suggestions**: All optimization suggestions displayed alongside the editor

---

## Architecture

### Backend (FastAPI)

#### New Router: `/ai-chat` (routers/ai_chat.py)

**Endpoints**:

1. **POST /ai-chat/chat** - Conversational AI Assistant
   ```json
   Request:
   {
     "ds_id": "mysql-db",
     "message": "Show all students enrolled in 2020",
     "conversation_history": [
       {"role": "user", "content": "..."},
       {"role": "assistant", "content": "..."}
     ],
     "current_sql": "SELECT * FROM students"  // Optional context
   }

   Response:
   {
     "message": "Here's a query to show all students enrolled in 2020:",
     "sql": "SELECT * FROM students WHERE enrollment_year = 2020",
     "action": "query_generated",
     "suggestions": [
       {
         "type": "index",
         "summary": "Add index on enrollment_year",
         "sql": "CREATE INDEX idx_students_enrollment_year ON students(enrollment_year);",
         "rationale": "Improves WHERE clause filtering"
       }
     ],
     "context": {
       "explanation": "Query filters by enrollment year",
       "next_steps": ["Add ORDER BY for sorting", "Add LIMIT if needed"]
     }
   }
   ```

2. **POST /ai-chat/validate-query** - Intelligent Query Validation
   ```json
   Request:
   {
     "ds_id": "mysql-db",
     "sql": "SELECT * FROM orders WHERE customer_id = 1"
   }

   Response:
   {
     "valid": false,
     "issues": [
       {
         "type": "missing_table",
         "message": "Table 'orders' does not exist",
         "suggestion": "Create table 'orders' or use an existing table"
       },
       {
         "type": "missing_condition",
         "message": "SELECT without WHERE may return many rows",
         "suggestion": "Add WHERE clause or use LIMIT"
       }
     ],
     "missing_tables": ["orders"],
     "has_conditions": true,
     "suggestions": [
       "CREATE TABLE: CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT, total DECIMAL(10,2));"
     ]
   }
   ```

**Key Features**:

- **Context-Aware**: Knows database schema, current SQL, and conversation history
- **Multi-Database Support**: Works with all 8 database types (PostgreSQL, MySQL, SQL Server, Oracle, SQLite, MongoDB, Redis, Cassandra)
- **Error Handling**: Graceful fallbacks for missing schema or LLM errors
- **Auto-Table Creation**: Detects non-existent tables and suggests CREATE TABLE statements with inferred columns

**Validation Logic**:

1. **Missing Tables**: Parses SQL for FROM/JOIN/INTO/UPDATE clauses, checks against schema
2. **Missing Conditions**: Detects queries without WHERE (warns for SELECT, errors for UPDATE/DELETE)
3. **Syntax Errors**: Uses EXPLAIN to validate query syntax
4. **Best Practices**: Warns about SELECT *, suggests improvements

---

### Frontend (React/TypeScript)

#### New Component: `SQLAssistant.tsx`

**Split-Screen Layout**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI SQL Assistant                                  │
├───────────────────────────────┬─────────────────────────────────────┤
│   SQL Editor (Left 50%)       │   Tabbed Panel (Right 50%)          │
│                               │                                     │
│  ┌─────────────────────────┐  │  [🤖 AI Chat] [💡 Suggestions] [✓ Validation]
│  │ SQL Textarea            │  │                                     │
│  │ - Real-time validation  │  │  Tab Content:                       │
│  │ - Syntax highlighting   │  │  - AI Chat: Conversational interface│
│  │ - Auto-resize           │  │  - Suggestions: Optimization tips   │
│  └─────────────────────────┘  │  - Validation: Real-time issues     │
│                               │                                     │
│  [▶ Execute & Analyze] [Clear] │                                     │
│                               │                                     │
│  📊 Schema: 10 tables         │                                     │
│  ⚠ 2 validation issues        │                                     │
└───────────────────────────────┴─────────────────────────────────────┘
```

**Features**:

1. **Left Panel - SQL Editor**:
   - Multi-line textarea with monospace font
   - Auto-validation on typing (1s debounce)
   - Visual feedback (red border for errors)
   - Execute & Analyze button (runs suggestions + validation)
   - Clear button (resets everything)
   - Schema stats (table count, validation issues)

2. **Right Panel - 3 Tabs**:

   **Tab 1: 🤖 AI Chat**
   - Conversational message history
   - User messages (blue background)
   - Assistant messages (white background, green border)
   - Input field with Send button
   - Welcome message with capabilities list
   - Auto-scroll to latest message
   - Loading indicator during AI processing

   **Tab 2: 💡 Suggestions**
   - List of AI-generated optimization suggestions
   - Each suggestion shows:
     - Category badge (index/rewrite/schema)
     - Title and summary
     - SQL code block (if applicable)
     - Apply button (inserts SQL into editor)
   - Color-coded by type:
     - Index: Purple
     - Rewrite: Orange
     - Schema: Green

   **Tab 3: ✓ Validation**
   - Real-time query validation results
   - Green checkmark if no issues
   - Issue cards showing:
     - Type (syntax/missing_table/missing_condition)
     - Message
     - Suggestion for fixing
   - Color-coded by severity:
     - Red: Syntax errors, missing tables (critical)
     - Yellow: Missing conditions, best practices (warnings)

**State Management**:

```typescript
// SQL Editor
const [sql, setSql] = useState('')
const [validationIssues, setValidationIssues] = useState([])

// AI Chat
const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
const [chatInput, setChatInput] = useState('')
const [chatLoading, setChatLoading] = useState(false)

// Suggestions
const [suggestions, setSuggestions] = useState<Suggestion[]>([])
const [suggestionsLoading, setSuggestionsLoading] = useState(false)

// UI
const [activeTab, setActiveTab] = useState<'chat' | 'suggestions' | 'validation'>('chat')
const [error, setError] = useState<string | null>(null)
```

**Auto-Synchronization**:

1. **Chat → SQL Editor**: AI-generated SQL automatically populates editor
2. **SQL Editor → Validation**: Auto-validates on typing (debounced)
3. **Execute → Suggestions**: Auto-analyzes and populates suggestions tab
4. **Suggestions → SQL Editor**: Apply button inserts SQL into editor

---

## Usage Examples

### Example 1: Natural Language Query Generation

**User Input (Chat)**:
```
Show me all students who enrolled in 2020 and are in department 1
```

**AI Response**:
```
Message: "Here's a query to retrieve students enrolled in 2020 from department 1:"

SQL:
SELECT * FROM students
WHERE enrollment_year = 2020 AND department_id = 1
ORDER BY last_name

Suggestions:
- Create composite index on (enrollment_year, department_id)
- Specify columns instead of SELECT *
```

**Result**:
- SQL auto-populates in editor
- Suggestions appear in Suggestions tab
- User can click "Apply" to add CREATE INDEX statement

---

### Example 2: Missing Table Detection

**User Query (Editor)**:
```sql
SELECT * FROM orders WHERE customer_id = 123
```

**Validation Result**:
```
⚠ Issue: missing_table
Table 'orders' does not exist

💡 Suggestion:
Create table 'orders' or use an existing table: students, professors, courses, etc.

Auto-Generated CREATE TABLE:
CREATE TABLE orders (
    customer_id INT PRIMARY KEY,
    order_date DATETIME,
    total DECIMAL(10,2)
);
```

**Chat Interaction**:
```
User: "Create the orders table"

AI: "I'll create the orders table based on your query context:"

SQL:
CREATE TABLE orders (
    customer_id INT,
    order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    total DECIMAL(10,2),
    INDEX idx_orders_customer_id (customer_id)
);
```

---

### Example 3: Query Without Conditions

**User Query (Editor)**:
```sql
DELETE FROM students
```

**Validation Result**:
```
❌ Issue: missing_condition
DELETE without WHERE clause will affect all rows

💡 Suggestion:
Add WHERE clause to limit affected rows

Example: DELETE FROM students WHERE enrollment_year < 2015
```

**Execution Blocked**: User cannot execute until adding WHERE clause

---

### Example 4: Query Optimization Workflow

**User Query (Editor)**:
```sql
SELECT * FROM mysqluniversitydb.fees
WHERE student_id = 1
ORDER BY due_date DESC
LIMIT 50
```

**Click "Execute & Analyze"**:

1. **Validation Tab (Auto-Opens if Issues)**:
   ```
   ⚠ SELECT * retrieves all columns, which may be inefficient
   💡 Specify only the columns you need
   ```

2. **Suggestions Tab (Auto-Populated)**:
   ```
   💡 Suggestion 1: Create composite index
   Category: index
   Summary: Eliminates filesort by covering both filtering and sorting
   SQL: CREATE INDEX idx_fees_student_id_due_date ON fees (student_id, due_date);
   [Apply Button]

   💡 Suggestion 2: Avoid SELECT *
   Category: rewrite
   Summary: Specify only required columns for better performance
   SQL: SELECT fee_id, student_id, amount, due_date, status FROM fees...
   [Apply Button]
   ```

3. **User Clicks "Apply" on Index Suggestion**:
   - SQL editor updates with:
   ```sql
   SELECT * FROM mysqluniversitydb.fees
   WHERE student_id = 1
   ORDER BY due_date DESC
   LIMIT 50

   CREATE INDEX idx_fees_student_id_due_date ON fees (student_id, due_date);
   ```

---

## Key Improvements Over Previous System

### Before:
- ❌ Separate SQL Editor and Query Optimizer panels (disconnected)
- ❌ No conversational AI (only rule-based suggestions)
- ❌ No missing table detection
- ❌ No context validation (could execute dangerous queries)
- ❌ Manual copy-paste between panels
- ❌ Suggestions only appear after execution

### After:
- ✅ **Integrated Split-Screen UI**: SQL editor and AI assistant side-by-side
- ✅ **Conversational AI Chat**: Natural language query generation
- ✅ **Real-Time Synchronization**: Chat ↔ Editor ↔ Suggestions
- ✅ **Intelligent Validation**: Prevents dangerous queries, suggests fixes
- ✅ **Auto-Table Creation**: Detects missing tables, generates CREATE statements
- ✅ **Context-Aware Suggestions**: Considers query intent, schema, and conversation history
- ✅ **One-Click Apply**: Suggestions insert directly into editor
- ✅ **Progressive Workflow**: Chat → SQL → Validate → Optimize → Execute

---

## Technical Implementation Details

### Backend Services

#### 1. AI Chat Service (routers/ai_chat.py)

**System Prompt Structure**:
```python
system_prompt = f"""You are an expert {db_type} database assistant.

Available tables: {', '.join(tables[:10])}

Schema summary:
{schema_summary}  # Top 5 tables with column names

Your capabilities:
1. Generate SQL from natural language
2. Optimize existing queries
3. Explain errors and suggest fixes
4. Suggest missing table creation
5. Validate query logic

Response format (JSON):
{
  "message": "...",
  "sql": "...",
  "action": "query_generated|query_optimized|...",
  "suggestions": [...],
  "context": {...}
}

Guidelines:
- Use {db_type}-specific syntax
- Warn if tables are missing
- Explain performance implications
```

**Missing Table Detection Algorithm**:
```python
def _detect_missing_tables(sql: str, existing_tables: List[str]) -> List[str]:
    # Extract table references using regex
    pattern = r'\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(pattern, sql, re.IGNORECASE)

    missing = []
    for table in matches:
        # Check case-insensitive match
        exists = any(table.lower() in t.lower() for t in existing_tables)
        if not exists:
            missing.append(table)

    return missing
```

**Auto-Table Creation**:
```python
def _suggest_table_creation(table_name: str, sql_context: str, db_type: str) -> str:
    # Infer columns from SQL context
    # 1. Extract columns from SELECT clause
    # 2. Extract columns from WHERE clause
    # 3. Generate CREATE TABLE with inferred types

    # Example output:
    """
    CREATE TABLE orders (
        id INT PRIMARY KEY,
        customer_id INT,
        order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        total DECIMAL(10,2)
    );
    """
```

#### 2. Validation Service (ai_chat.py)

**Validation Checks**:

1. **Missing Tables**:
   - Parse SQL for table references
   - Compare against schema
   - Generate CREATE TABLE suggestions

2. **Missing WHERE Conditions**:
   ```python
   has_where = bool(re.search(r'\bWHERE\b', sql, re.IGNORECASE))

   if not has_where:
       if re.search(r'\b(UPDATE|DELETE)\b', sql):
           # Critical: affects all rows
           issue = "UPDATE/DELETE without WHERE will affect ALL rows"
       elif re.search(r'\bSELECT\b', sql):
           # Warning: may return too many rows
           issue = "SELECT without WHERE may return many rows"
   ```

3. **Syntax Validation**:
   ```python
   try:
       agent.explain(sql, analyze=False)
       # If EXPLAIN succeeds, syntax is valid
   except Exception as e:
       # Syntax error: e.message contains details
   ```

---

### Frontend Components

#### API Client (api/client.ts)

```typescript
export const aiChatApi = {
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    return apiRequest<ChatResponse>('/ai-chat/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  validateQuery: async (request: ValidateQueryRequest): Promise<ValidateQueryResponse> => {
    return apiRequest<ValidateQueryResponse>('/ai-chat/validate-query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },
};
```

#### SQLAssistant Component Logic

**Auto-Validation on Type**:
```typescript
useEffect(() => {
  const timer = setTimeout(() => {
    if (sql.trim()) {
      validateSQL();  // Debounced validation
    }
  }, 1000);

  return () => clearTimeout(timer);
}, [sql]);
```

**Chat Message Sending**:
```typescript
const sendChatMessage = async () => {
  const response = await aiChatApi.chat({
    ds_id: dataSourceId,
    message: chatInput,
    conversation_history: chatHistory,
    current_sql: sql || undefined,
  });

  // Update SQL if AI generated it
  if (response.sql) {
    setSql(response.sql);
  }

  // Show suggestions if any
  if (response.suggestions.length > 0) {
    setSuggestions([...response.suggestions, ...suggestions]);
    setActiveTab('suggestions');
  }
};
```

**Apply Suggestion**:
```typescript
const applySuggestion = (suggestion: Suggestion) => {
  if (suggestion.category === 'schema') {
    // CREATE TABLE: append
    setSql(prev => `${prev}\n\n${suggestion.sql_fix}`);
  } else if (suggestion.category === 'rewrite') {
    // Rewrite: replace
    setSql(suggestion.sql_fix);
  } else {
    // Others: append
    setSql(prev => `${prev}\n\n${suggestion.sql_fix}`);
  }
};
```

---

## Testing Checklist

### Backend Tests

```bash
# 1. Start backend
python run.py

# 2. Register datasource
curl -X POST http://127.0.0.1:8000/datasources \
  -H "Content-Type: application/json" \
  -d '{"id":"mysql-db","engine":"mysql","dsn":"mysql://root:pass@localhost:3306/db"}'

# 3. Test AI Chat
curl -X POST http://127.0.0.1:8000/ai-chat/chat \
  -H "Content-Type: application/json" \
  -d '{
    "ds_id": "mysql-db",
    "message": "Show all students enrolled in 2020"
  }'

# 4. Test Validation
curl -X POST http://127.0.0.1:8000/ai-chat/validate-query \
  -H "Content-Type: application/json" \
  -d '{
    "ds_id": "mysql-db",
    "sql": "SELECT * FROM orders WHERE customer_id = 1"
  }'
```

### Frontend Tests

1. **Layout**:
   - [ ] Three-panel layout loads correctly
   - [ ] Left sidebar: Connection Panel (280px)
   - [ ] Middle sidebar: DB Explorer (300px)
   - [ ] Right main: SQL Assistant (flex 1)

2. **SQL Editor**:
   - [ ] Textarea accepts input
   - [ ] Auto-validation triggers after 1 second
   - [ ] Validation issues show red border
   - [ ] Execute button triggers suggestions
   - [ ] Clear button resets everything

3. **AI Chat Tab**:
   - [ ] Welcome message displays
   - [ ] User can send messages
   - [ ] Loading indicator shows during processing
   - [ ] AI responses appear with green border
   - [ ] Generated SQL auto-populates editor
   - [ ] Auto-scrolls to latest message

4. **Suggestions Tab**:
   - [ ] Displays after Execute button
   - [ ] Shows AI suggestions with Apply buttons
   - [ ] Apply button inserts SQL into editor
   - [ ] Color-coded by category

5. **Validation Tab**:
   - [ ] Shows checkmark when no issues
   - [ ] Displays validation issues
   - [ ] Auto-opens when critical errors detected
   - [ ] Color-coded by severity

6. **Synchronization**:
   - [ ] Chat generates SQL → Editor updates
   - [ ] Editor changes → Validation updates
   - [ ] Execute → Suggestions populate
   - [ ] Apply suggestion → Editor updates

---

## Deployment

### Backend

```bash
# Production mode
export ENV=prod
python run.py
# Server runs on http://127.0.0.1:8000
```

### Frontend

```bash
cd tauri-app

# Development (browser)
npm run dev
# Opens http://localhost:5173

# Development (Tauri desktop)
npm run tauri dev

# Production build
npm run tauri build
# Creates installers in src-tauri/target/release/bundle/
```

---

## Future Enhancements

1. **Multi-Tab SQL Editor**: Support multiple query tabs
2. **Query History**: Save and recall previous queries
3. **Suggestion Favorites**: Bookmark frequently used optimizations
4. **Batch Apply**: Select multiple suggestions and apply at once
5. **Export to Migration**: Convert suggestions to migration scripts
6. **Visual Query Builder**: Drag-and-drop query construction
7. **Performance Benchmarking**: Before/after execution time comparison
8. **Team Collaboration**: Share queries and suggestions
9. **Custom Templates**: User-defined query templates
10. **Dark Mode**: UI theme toggle

---

## Troubleshooting

### Issue: AI Chat Returns Error

**Cause**: LLM (Ollama) not running or model not pulled

**Fix**:
```bash
# Check Ollama status
ollama list

# Pull model if missing
ollama pull qwen2.5:7b-instruct

# Verify endpoint
curl http://127.0.0.1:11434/api/tags
```

### Issue: Validation Always Shows "Missing Table"

**Cause**: Schema not loaded correctly

**Fix**:
- Check datasource connection
- Verify `analyzeApi.getSchema()` returns tables
- Check browser console for errors

### Issue: Suggestions Not Appearing

**Cause**: SQL query is empty or invalid

**Fix**:
- Enter a valid SQL query
- Check Validation tab for syntax errors
- Ensure datasource is selected

### Issue: Apply Button Not Working

**Cause**: Suggestion has no `sql_fix` field

**Fix**:
- This is expected for "note" type suggestions (advisory only)
- Only index/rewrite/schema suggestions have Apply button

---

## API Documentation

Full API documentation available at: **http://127.0.0.1:8000/docs** (Swagger UI)

Key endpoints:
- `POST /ai-chat/chat` - Conversational AI
- `POST /ai-chat/validate-query` - Query validation
- `POST /suggestions/analyze` - Get optimization suggestions
- `POST /suggestions/apply_direct` - Apply suggestions to database

---

## Summary

The AI SQL Assistant transforms the Query Optimizer from a static suggestion panel into an intelligent, conversational AI agent that:

✅ **Generates queries from natural language**
✅ **Validates queries before execution**
✅ **Detects and auto-creates missing tables**
✅ **Provides context-aware optimization suggestions**
✅ **Synchronizes seamlessly between chat, editor, and suggestions**
✅ **Prevents dangerous queries (DELETE/UPDATE without WHERE)**
✅ **Supports all 8 database types**

This creates a smooth, intelligent workflow where users can:
1. Describe what they want in plain English
2. Review and edit the generated SQL
3. See validation issues and suggestions
4. Apply optimizations with one click
5. Execute with confidence

The system acts as a senior DBA assistant, guiding users to write better, faster, safer SQL queries.