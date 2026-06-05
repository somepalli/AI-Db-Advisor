# 🤖 AI DB Advisor

**Intelligent Multi-Database Performance Optimization System with AI-Powered Chat Assistant**

AI DB Advisor is a comprehensive database performance optimization platform that combines rule-based analysis with AI-powered recommendations. It features a modern desktop application built with Tauri and React, backed by a FastAPI server with intelligent context-aware SQL generation.

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)
![Tauri](https://img.shields.io/badge/Tauri-v2-FFC131.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 🚀 Run with Docker (fastest)

No toolchains needed — run the backend + web UI with one command:

```bash
cp .env.docker.example .env     # choose your LLM (Ollama / OpenAI / Anthropic)
docker compose up --build       # then open http://localhost:8080
```

See **[DOCKER.md](DOCKER.md)** for LLM options, persistence, and database-driver notes.
For native/desktop development, see **[INSTALL.md](INSTALL.md)**.

---

## ✨ Features

### 🎯 AI-Powered SQL Assistant
- **Conversational Query Generation**: Generate SQL queries from natural language
- **Intelligent Context Analysis**: Uses smart table selection and sample data for accurate suggestions
- **Real-time Validation**: Validates queries before execution
- **Chat History**: Persistent chat sessions with semantic search across conversations
- **Multi-turn Conversations**: Maintains context across multiple messages

### 🗄️ Multi-Database Support (8 Database Types)

**SQL Databases:**
- PostgreSQL
- MySQL/MariaDB
- SQL Server
- Oracle Database
- SQLite

**NoSQL Databases:**
- MongoDB (Document Store)
- Redis (Key-Value Store)
- Apache Cassandra (Wide-Column Store)

### 🔍 Performance Analysis
- **Query Execution Plans**: Visual EXPLAIN plans for all database types
- **Index Recommendations**: AI + rule-based index suggestions with duplicate prevention
- **Query Rewrite Suggestions**: Performance optimization recommendations
- **Database Statistics**: Connection pools, table sizes, lock monitoring
- **Top Queries Analysis**: Identify slow queries across databases

### 🖥️ Modern Desktop UI
- **Tauri v2 Desktop App**: Lightweight alternative to Electron
- **4-Panel Layout**: Connections, Database Explorer, SQL Editor, AI Chat
- **SQL Autocomplete**: Intelligent autocomplete for tables, columns, and keywords
- **Real-time Syntax Validation**: Instant feedback on query syntax
- **Session Management**: Save and switch between chat sessions

### 🧠 Intelligent Context Builder
- **Smart Table Selection**: Relevance scoring algorithm to select the most relevant tables
- **Sample Data Inclusion**: Provides actual data examples for better AI understanding
- **Relationship Detection**: Auto-detects foreign keys and table relationships
- **Column Type Awareness**: Full schema with data types, nullability, and constraints

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Tauri Desktop App                      │
│              (React + TypeScript + Vite)                 │
│  ┌──────────┬──────────┬──────────┬─────────────────┐  │
│  │Connection│  DB      │   SQL    │  AI Chat        │  │
│  │  Panel   │ Explorer │  Editor  │  Assistant      │  │
│  └──────────┴──────────┴──────────┴─────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP REST API
                       ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend (Python)                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Routers: /datasources, /analyze, /ai-chat       │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  Services: Context Builder, AI Client, Advisors  │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  Agents: PostgreSQL, MySQL, MongoDB, etc.        │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                              ▼
┌──────────────────┐          ┌──────────────────┐
│ Multi-Databases  │          │  Ollama LLM      │
│ (8 DB types)     │          │ + ChromaDB       │
└──────────────────┘          └──────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.13+**
- **Node.js 18+** and npm
- **Ollama** (for AI features)
- **Rust** (for Tauri desktop app, optional)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-db-advisor.git
cd ai-db-advisor
```

### 2. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server
python run.py
```

Server runs on: `http://127.0.0.1:8000`
- API Docs: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/healthz

### 3. Frontend Setup (Web Interface)

```bash
cd tauri-app
npm install

# Run Vite dev server (browser-based)
npm run dev
```

Opens on: `http://localhost:5173`

### 4. Desktop App (Optional)

```bash
# Install Rust (if not already installed)
# Windows: winget install Rustlang.Rustup
# macOS/Linux: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Run Tauri desktop app
npm run tauri dev
```

### 5. Setup Ollama (AI Features)

```bash
# Install Ollama
# Visit: https://ollama.ai

# Pull the default model
ollama pull qwen2.5:7b-instruct

# Verify Ollama is running
curl http://127.0.0.1:11434/api/tags
```

---

## 📖 Usage

### Connecting to a Database

**PostgreSQL Example:**
```
ID: my-postgres-db
Engine: postgres
DSN: postgresql://user:password@localhost:5432/database
```

**MongoDB Example:**
```
ID: my-mongo-db
Engine: mongodb
DSN: mongodb://user:password@localhost:27017/database
```

**Supported DSN Formats:**
- **PostgreSQL**: `postgresql://user:pass@host:5432/db`
- **MySQL**: `mysql://user:pass@host:3306/db`
- **SQL Server**: `mssql://user:pass@host:1433/db`
- **Oracle**: `oracle://user:pass@host:1521/service`
- **MongoDB**: `mongodb://user:pass@host:27017/db`
- **Redis**: `redis://host:6379/0`
- **SQLite**: `sqlite:///path/to/database.db`
- **Cassandra**: `cassandra://host:9042/keyspace`

### Using the AI Chat Assistant

**Natural Language Queries:**
```
User: "Show all students enrolled in 2020"
AI: Generates → SELECT * FROM students WHERE enrollment_year = 2020
```

**Query Optimization:**
```
User: "Optimize this query: SELECT * FROM students"
AI: Suggests → Use specific columns, add WHERE clause, create indexes
```

**Error Explanation:**
```
User: "Why is this query slow?"
AI: Analyzes EXPLAIN plan and suggests improvements
```

**Table Creation:**
```
User: "Create a table for storing customer orders"
AI: Generates CREATE TABLE with appropriate columns and types
```

### Chat History

- **View Past Sessions**: Click the 💬 icon to see all chat sessions
- **Session Titles**: Auto-generated from first message
- **Semantic Search**: Search across all conversations
- **Session Switching**: Load previous conversations with full history
- **Delete Sessions**: Remove old chat sessions

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# LLM Configuration
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b-instruct
LLM_ENDPOINT=http://127.0.0.1:11434

# Environment
ENV=dev
```

### Supported LLM Models

- `qwen2.5:7b-instruct` (default, recommended)
- `llama3.1:8b`
- `mistral:7b`
- `codellama:7b`

---

## 📊 Key Components

### Backend (FastAPI)

**Service Layer:**
- `context_builder.py`: Intelligent context generation with table relevance scoring
- `ai_client.py`: LLM client wrapper for Ollama
- `chat_history.py`: ChromaDB-based chat persistence with semantic search
- `advisor.py`: Rule-based optimization recommendations
- `super_agent.py`: AI suggestion orchestration

**Database Agents:**
- `postgres_agent.py`: PostgreSQL via psycopg
- `mysql_agent.py`: MySQL/MariaDB via pymysql
- `mongodb_agent.py`: MongoDB via pymongo
- `redis_agent.py`: Redis via redis-py
- `cassandra_agent.py`: Cassandra via cassandra-driver
- `sqlserver_agent.py`: SQL Server via pyodbc
- `oracle_agent.py`: Oracle via cx_Oracle
- `sqlite_agent.py`: SQLite via stdlib

**API Endpoints:**
- `/datasources` - Manage database connections
- `/analyze/{ds_id}/*` - Query analysis and optimization
- `/ai-chat/chat` - Conversational AI assistant
- `/ai-chat/validate-query` - Real-time query validation
- `/chat-history/*` - Chat session management

### Frontend (React + Tauri)

**Components:**
- `ConnectionPanel.tsx`: Multi-database connection management
- `DBExplorer.tsx`: Schema browser with optimization features
- `SQLAssistant.tsx`: Main SQL editor with AI chat integration
- `ChatHistoryDropdown.tsx`: Session history with Cursor-like UI
- `QueryAnalyzer.tsx`: Query analysis results display

**API Client:**
- `api/client.ts`: Type-safe API wrapper with full endpoint coverage

---

## 🧪 Testing

```bash
# Backend tests
cd .venv/app
pytest

# Frontend tests
cd tauri-app
npm run test
```

---

## 🎯 Advanced Features

### Intelligent Context Builder

**Query Understanding:**
```python
Query: "Show students enrolled in 2020"
Keywords: ['students', 'enrolled', '2020']

Table Scoring:
- students: 15 points (table match + enrollment_year column)
- enrollments: 5 points (keyword match)
- courses: 0 points

Selected: students table ✅
```

**Enhanced Schema Context:**
```
students:
  - student_id (integer) NOT NULL
  - first_name (character varying)
  - enrollment_year (integer)  ← AI sees actual column!

Sample Data:
  1. student_id=1, enrollment_year=2020
  2. student_id=2, enrollment_year=2019

Relationships:
  students.department_id → departments
```

### Index Validation System

**3-Layer Duplicate Prevention:**
1. Advisor layer checks existing indexes
2. AI suggestion filter validates recommendations
3. Final deduplication before returning results

**Prevents:**
```sql
-- Won't suggest if already exists:
CREATE INDEX idx_students_enrollment_year ON students(enrollment_year);
```

### Chat History with Semantic Search

**Vector Database (ChromaDB):**
- Stores all conversations with embeddings
- Semantic search across all messages
- Session-based isolation per datasource
- Similarity scoring for relevant results

**Example Search:**
```
Query: "enrollment queries"
Results:
  1. "Show all students enrolled in 2020" (95% match)
  2. "Find courses by enrollment count" (87% match)
```

---

## 📦 Database-Specific Requirements

### PostgreSQL
- **Extension** (recommended): `pg_stat_statements`
- Falls back to `pg_stat_activity` if unavailable

### SQL Server
- **ODBC Driver 17** for SQL Server
- DMV access permissions

### Oracle Database
- **Oracle Instant Client** required
- V$ view permissions

### NoSQL Databases
- No special requirements
- Redis: Enable slowlog for query tracking

---

## 🛠️ Development

### Project Structure

```
ai-db-advisor/
├── .venv/app/              # FastAPI Backend
│   ├── routers/            # API endpoints
│   ├── services/           # Business logic
│   │   ├── context_builder.py
│   │   ├── ai_client.py
│   │   └── chat_history.py
│   ├── agents/             # Database agents
│   └── utils/              # Helpers
│
├── tauri-app/              # Tauri Desktop App
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── api/            # API client
│   │   └── types/          # TypeScript types
│   └── src-tauri/          # Rust backend
│
├── requirements.txt        # Python dependencies
├── run.py                  # Backend entry point
└── README.md              # This file
```

### Adding New Database Support

1. Create agent class inheriting from `BaseAgent`
2. Implement all required methods
3. Add driver to `requirements.txt`
4. Register in `registry.py`
5. Update frontend engine dropdown
6. Add DSN format documentation

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **FastAPI** - Modern web framework
- **Ollama** - Local LLM inference
- **Tauri** - Lightweight desktop framework
- **ChromaDB** - Vector database for chat history
- **Sentence Transformers** - Embedding models
- **SQLGlot** - SQL parsing and analysis

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/ai-db-advisor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/ai-db-advisor/discussions)

---

## 🗺️ Roadmap

- [ ] Support for additional databases (Elasticsearch, Neo4j)
- [ ] Query execution history and favorites
- [ ] Export optimization reports
- [ ] Database migration suggestions
- [ ] Multi-language support
- [ ] Cloud deployment options
- [ ] Performance benchmarking
- [ ] Automated testing suite
- [ ] Dark mode UI

---

**Made with ❤️ by the AI DB Advisor Team**

---
