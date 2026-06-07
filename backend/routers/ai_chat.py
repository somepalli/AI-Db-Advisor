"""
AI Chat Router - Conversational SQL Assistant
Provides intelligent query generation, optimization, and table creation assistance.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import json
import re
import asyncio
from ..deps import resolve_agent
from ..services.ai_client import LLMClient
from ..services import chat_history
from ..services.context_builder import build_ai_context
from ..services.gated_context import build_gated_context, GATED_ENGINES
from ..services.tool_registry import scrub_literals, normalize_sql
from ..services.llm_settings import resolve_provider_trust
from ..services.mcp_client import get_mcp_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-chat", tags=["ai-chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    ds_id: str
    message: str
    conversation_history: List[ChatMessage] = []
    current_sql: Optional[str] = None  # SQL from editor for context
    session_id: Optional[str] = None  # Session ID for persistence
    save_to_history: bool = True  # Auto-save to vector DB


class ChatResponse(BaseModel):
    message: str
    sql: Optional[str] = None
    suggestions: List[Dict[str, Any]] = []
    action: str  # "query_generated" | "query_optimized" | "table_created" | "error_explained" | "general_help"
    context: Dict[str, Any] = {}


class ValidateQueryRequest(BaseModel):
    ds_id: str
    sql: str


class ValidateQueryResponse(BaseModel):
    valid: bool
    issues: List[Dict[str, str]]  # [{type: "missing_table"|"missing_condition"|"syntax", message: "...", suggestion: "..."}]
    missing_tables: List[str]
    has_conditions: bool
    suggestions: List[str]


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(body: ChatRequest):
    """
    Conversational AI assistant for SQL queries.

    Capabilities:
    - Generate SQL from natural language
    - Optimize existing queries
    - Explain errors and suggest fixes
    - Create missing tables automatically
    - Provide context-aware suggestions
    """
    try:
        agent = resolve_agent(body.ds_id)
        llm = LLMClient()
        db_type = agent.get_db_type().upper()
        engine = agent.get_db_type().lower()
        trust = resolve_provider_trust()

        logger.info(f"AI Chat Request - DB: {db_type}, trust={trust}, Message: {body.message[:100]}...")

        # Default the message defensively: scrubbed for hosted Postgres so a context-build
        # failure can never leave literals in the prompt; the gated path re-confirms below.
        safe_message = (
            scrub_literals(body.message)
            if (engine in GATED_ENGINES and trust == "hosted") else body.message
        )

        # Get schema context. PostgreSQL and MySQL use the provider-trust gated path (metadata
        # tools + sample rows only for local models); other engines keep the legacy builder.
        try:
            schema = agent.get_schema()
            tables = list(schema.get("tables", {}).keys())

            if engine in GATED_ENGINES:
                context_str, safe_message = await build_gated_context(
                    ds_id=body.ds_id, engine=engine, trust=trust,
                    user_message=body.message, current_sql=body.current_sql,
                )
            else:
                context_str = build_ai_context(
                    ds_id=body.ds_id,
                    user_message=body.message,
                    current_sql=body.current_sql,
                    max_tables=5,
                    include_sample_data=True
                )
        except Exception as e:
            logger.warning(f"Context building failed: {e}")
            tables = []
            context_str = "Schema unavailable"

        # Build conversation context with enhanced schema
        system_prompt = f"""You are an expert {db_type} database assistant with deep understanding of database schemas and data.

DATABASE CONTEXT:
{context_str}

Your capabilities:
1. Generate SQL queries from natural language descriptions
2. Optimize existing queries for better performance
3. Explain query errors and suggest fixes
4. Suggest creating missing tables with appropriate schema
5. Validate query logic and suggest improvements

Response format (JSON):
{{
  "message": "Your conversational response to the user",
  "sql": "Generated or optimized SQL query (if applicable)",
  "action": "query_generated|query_optimized|table_created|error_explained|general_help",
  "suggestions": [
    {{"type": "index"|"rewrite"|"create_table"|"add_condition", "summary": "...", "sql": "..."}}
  ],
  "context": {{"explanation": "Why you suggested this", "next_steps": ["...", "..."]}}
}}

CRITICAL GUIDELINES:
- ALWAYS analyze the provided schema carefully, including column names and data types
- LOOK at the sample data to understand the actual data format and values
- Use EXACT column names from the schema (case-sensitive)
- Understand relationships between tables (look for _id columns and foreign keys)
- For year/date queries, check which columns contain year data:
  * If you see 'enrollment_year' column, use it for enrollment year queries
  * If you see 'created_at' or 'date' columns, extract year from those
  * DO NOT assume columns exist - only use what's in the schema
- Always provide executable SQL when generating queries
- For {db_type}, use appropriate syntax and best practices
- If tables are missing, suggest CREATE TABLE statements
- If query lacks conditions, warn the user and suggest adding them
- Keep responses concise and actionable
- Explain performance implications when relevant

EXAMPLE:
User: "Show all students enrolled in 2020"
Analysis: Check schema for 'students' table → find 'enrollment_year' column → use it
Correct SQL: SELECT * FROM students WHERE enrollment_year = 2020
Wrong SQL: SELECT * FROM enrollments WHERE semester LIKE '%2020%' (if 'semester' column doesn't exist)
"""

        # Build user message with context
        user_content_parts = []

        if body.current_sql:
            # Literals in the editor SQL are an egress channel too: scrub them for hosted
            # gated-engine models the same way the NL question is scrubbed above.
            safe_sql = (
                normalize_sql(body.current_sql)
                if (engine in GATED_ENGINES and trust == "hosted") else body.current_sql
            )
            user_content_parts.append(f"Current SQL in editor:\n```sql\n{safe_sql}\n```\n")

        # safe_message == body.message for local trust; literals scrubbed for hosted models.
        user_content_parts.append(f"User request: {safe_message}")

        user_content = "\n".join(user_content_parts)

        # Prepare conversation history
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (last 5 messages for context)
        for msg in body.conversation_history[-5:]:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_content})

        logger.info(f"Calling LLM with {len(messages)} messages...")

        # Call LLM
        try:
            response = llm.chat(messages, json_response=True)

            logger.info(f"LLM Response: {json.dumps(response, indent=2)[:500]}...")

            # Parse response
            if isinstance(response, dict):
                message = response.get("message", "")
                sql = response.get("sql")
                action = response.get("action", "general_help")
                suggestions = response.get("suggestions", [])
                context = response.get("context", {})

                # Post-process: Validate generated SQL
                if sql:
                    sql = _clean_sql(sql)

                    # Check if SQL references missing tables
                    missing_tables = _detect_missing_tables(sql, tables)
                    if missing_tables:
                        context["missing_tables"] = missing_tables
                        context["warning"] = f"Query references non-existent tables: {', '.join(missing_tables)}"

                        # Auto-suggest table creation
                        for table_name in missing_tables:
                            create_table_sql = _suggest_table_creation(table_name, sql, db_type)
                            suggestions.append({
                                "type": "create_table",
                                "summary": f"Create missing table '{table_name}'",
                                "sql": create_table_sql,
                                "rationale": f"Table '{table_name}' does not exist in the database"
                            })

                        message += f"\n\n⚠️ Note: The query references tables that don't exist: {', '.join(missing_tables)}. I've suggested CREATE TABLE statements above."

                # Save to chat history (if enabled)
                if body.save_to_history and body.session_id:
                    try:
                        # Save user message
                        chat_history.save_message(
                            ds_id=body.ds_id,
                            session_id=body.session_id,
                            role="user",
                            content=body.message,
                            sql_context=body.current_sql
                        )

                        # Save assistant response
                        chat_history.save_message(
                            ds_id=body.ds_id,
                            session_id=body.session_id,
                            role="assistant",
                            content=message,
                            sql_context=sql
                        )

                        logger.info(f"Saved chat messages to history for session: {body.session_id}")
                    except Exception as e:
                        logger.warning(f"Failed to save chat history: {e}")
                        # Don't fail the request if history save fails

                # Fetch MCP suggestions asynchronously (if available)
                mcp_suggestions = await _fetch_mcp_suggestions(body.ds_id, sql or body.current_sql)

                # Merge AI and MCP suggestions
                all_suggestions = suggestions + mcp_suggestions

                # Add context about MCP suggestions if any were fetched
                if mcp_suggestions:
                    context["mcp_suggestions_count"] = len(mcp_suggestions)
                    context["total_suggestions"] = len(all_suggestions)

                return ChatResponse(
                    message=message,
                    sql=sql,
                    suggestions=all_suggestions,
                    action=action,
                    context=context
                )
            else:
                # Fallback for non-JSON response
                return ChatResponse(
                    message=str(response),
                    action="general_help",
                    context={"note": "LLM returned non-JSON response"}
                )

        except Exception as llm_error:
            logger.error(f"LLM call failed: {llm_error}")
            raise HTTPException(500, f"AI processing failed: {str(llm_error)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Chat failed: {str(e)}")


@router.post("/validate-query", response_model=ValidateQueryResponse)
async def validate_query(body: ValidateQueryRequest):
    """
    Validate query context and suggest improvements.

    Checks for:
    - Missing WHERE conditions (dangerous for large tables)
    - Non-existent tables
    - Syntax errors
    - Performance concerns
    """
    try:
        agent = resolve_agent(body.ds_id)
        db_type = agent.get_db_type().upper()

        logger.info(f"Validating query for {db_type}: {body.sql[:100]}...")

        issues = []
        suggestions = []

        # Get schema
        try:
            schema = agent.get_schema()
            tables = list(schema.get("tables", {}).keys())
        except Exception as e:
            logger.warning(f"Schema unavailable: {e}")
            tables = []

        # 1. Check for missing tables
        missing_tables = _detect_missing_tables(body.sql, tables)
        if missing_tables:
            for table in missing_tables:
                issues.append({
                    "type": "missing_table",
                    "message": f"Table '{table}' does not exist",
                    "suggestion": f"Create table '{table}' or use an existing table: {', '.join(tables[:5])}"
                })

                # Suggest table creation
                create_sql = _suggest_table_creation(table, body.sql, db_type)
                suggestions.append(f"CREATE TABLE: {create_sql}")

        # 2. Check for missing WHERE conditions
        has_conditions = _has_where_clause(body.sql)
        if not has_conditions:
            if re.search(r'\b(UPDATE|DELETE)\b', body.sql, re.IGNORECASE):
                issues.append({
                    "type": "missing_condition",
                    "message": "UPDATE/DELETE without WHERE clause will affect all rows",
                    "suggestion": "Add WHERE clause to limit affected rows"
                })
            elif re.search(r'\bSELECT\b', body.sql, re.IGNORECASE):
                # Only warn for SELECT if table is likely large
                table_match = re.search(r'FROM\s+(\w+)', body.sql, re.IGNORECASE)
                if table_match:
                    table_name = table_match.group(1)
                    issues.append({
                        "type": "missing_condition",
                        "message": f"SELECT from '{table_name}' without WHERE may return many rows",
                        "suggestion": f"Consider adding WHERE clause to filter results, or use LIMIT if scanning all rows is intentional"
                    })
                    suggestions.append(f"Add condition: WHERE <column> = <value>")
                    suggestions.append(f"Or add limit: LIMIT 100")

        # 3. Check for SELECT *
        if re.search(r'SELECT\s+\*', body.sql, re.IGNORECASE):
            issues.append({
                "type": "best_practice",
                "message": "SELECT * retrieves all columns, which may be inefficient",
                "suggestion": "Specify only the columns you need"
            })

        # 4. Try to validate syntax with EXPLAIN
        syntax_valid = True
        try:
            agent.explain(body.sql, analyze=False)
        except Exception as e:
            syntax_valid = False
            error_msg = str(e)
            issues.append({
                "type": "syntax",
                "message": f"Query syntax error: {error_msg[:200]}",
                "suggestion": "Fix syntax errors before executing"
            })

        valid = len([i for i in issues if i["type"] in ["syntax", "missing_table"]]) == 0

        logger.info(f"Validation result: valid={valid}, issues={len(issues)}")

        return ValidateQueryResponse(
            valid=valid,
            issues=issues,
            missing_tables=missing_tables,
            has_conditions=has_conditions,
            suggestions=suggestions
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(500, f"Validation failed: {str(e)}")




def _clean_sql(sql: str) -> str:
    """Remove markdown code blocks and extra whitespace."""
    # Remove markdown code blocks
    sql = re.sub(r'```sql\n', '', sql)
    sql = re.sub(r'```\n?', '', sql)

    # Remove leading/trailing whitespace
    sql = sql.strip()

    return sql


def _detect_missing_tables(sql: str, existing_tables: List[str]) -> List[str]:
    """Detect tables referenced in SQL that don't exist."""
    # Extract table names from SQL (simplified pattern)
    # Matches: FROM table, JOIN table, INTO table, UPDATE table
    pattern = r'\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z_][a-zA-Z0-9_]*\.?[a-zA-Z0-9_]*)'
    matches = re.findall(pattern, sql, re.IGNORECASE)

    missing = []
    for table in matches:
        # Normalize table name (handle schema.table)
        table_name = table.split('.')[-1].strip()

        # Check if exists (case-insensitive, check with and without schema)
        exists = any(
            table_name.lower() in existing_table.lower()
            for existing_table in existing_tables
        )

        if not exists and table_name not in missing:
            missing.append(table_name)

    return missing


def _has_where_clause(sql: str) -> bool:
    """Check if SQL has WHERE clause."""
    return bool(re.search(r'\bWHERE\b', sql, re.IGNORECASE))


def _suggest_table_creation(table_name: str, sql_context: str, db_type: str) -> str:
    """
    Generate CREATE TABLE suggestion based on context.
    Infers columns from SQL query context.
    """
    # Try to infer columns from SQL
    columns = []

    # Extract columns from SELECT clause
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_context, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_clause = select_match.group(1)
        if select_clause.strip() != '*':
            # Parse column names (simplified)
            col_parts = [c.strip() for c in select_clause.split(',')]
            for col in col_parts:
                # Remove aliases (AS ...)
                col_name = re.sub(r'\s+AS\s+\w+', '', col, flags=re.IGNORECASE).strip()
                # Extract base column name
                col_name = col_name.split('.')[-1]
                if col_name and col_name.upper() not in ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']:
                    columns.append(col_name)

    # Extract columns from WHERE clause
    where_matches = re.findall(r'(\w+)\s*[=<>!]', sql_context, re.IGNORECASE)
    for col in where_matches:
        if col.upper() not in ['AND', 'OR', 'NOT', 'IN', 'EXISTS']:
            if col not in columns:
                columns.append(col)

    # Generate CREATE TABLE
    if columns:
        # Generate columns with inferred types
        col_defs = []
        for i, col in enumerate(columns[:10]):  # Max 10 columns
            if i == 0:
                # First column is likely ID
                if db_type in ["POSTGRES", "MYSQL", "MARIADB"]:
                    col_defs.append(f"    {col} INTEGER PRIMARY KEY")
                else:
                    col_defs.append(f"    {col} INT PRIMARY KEY")
            else:
                # Others are VARCHAR by default
                col_defs.append(f"    {col} VARCHAR(255)")

        col_definitions = ",\n".join(col_defs)
    else:
        # Fallback: generic table structure
        if db_type in ["POSTGRES", "MYSQL", "MARIADB"]:
            col_definitions = """    id INTEGER PRIMARY KEY,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"""
        else:
            col_definitions = """    id INT PRIMARY KEY,
    name VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP"""

    create_sql = f"""CREATE TABLE {table_name} (
{col_definitions}
);"""

    return create_sql


async def _fetch_mcp_suggestions(ds_id: str, sql: Optional[str]) -> List[Dict[str, Any]]:
    """
    Fetch MCP suggestions asynchronously using direct postgres-mcp integration.
    Falls back gracefully if MCP is not available.
    """
    try:
        # Get datasource to check if it's PostgreSQL
        agent = resolve_agent(ds_id)
        db_type = agent.get_db_type().upper()

        # Only use postgres-mcp for PostgreSQL databases
        if db_type != "POSTGRES":
            logger.info(f"Skipping postgres-mcp for non-PostgreSQL database: {db_type}")
            return []

        # Get DSN from agent
        from ..config import settings
        ds_config = settings.DATASOURCES.get(ds_id)
        if not ds_config:
            logger.warning(f"Datasource config not found: {ds_id}")
            return []

        dsn = ds_config.get("dsn")
        if not dsn:
            logger.warning(f"DSN not found for datasource: {ds_id}")
            return []

        # Use direct postgres-mcp integration
        logger.info(f"Fetching postgres-mcp suggestions for {ds_id}")

        from ..services.postgres_mcp_direct import get_optimization_suggestions

        # Get optimization suggestions
        mcp_suggestions_raw = await get_optimization_suggestions(
            dsn=dsn,
            query=sql,
            max_suggestions=5
        )

        # Convert to AI suggestion format
        ai_format_suggestions = []
        for mcp_sug in mcp_suggestions_raw:
            ai_format_suggestions.append({
                "type": mcp_sug.get("type", "optimization"),
                "summary": mcp_sug.get("description", ""),
                "sql": mcp_sug.get("sql", ""),
                "rationale": mcp_sug.get("rationale", ""),
                "risk": mcp_sug.get("risk_level", "low"),
                "mcp_tool": mcp_sug.get("mcp_tool", ""),
                "expected_gain": mcp_sug.get("expected_gain", "Performance improvement expected"),
                "is_mcp": True,  # Flag to identify MCP suggestions
                "category": mcp_sug.get("category", "optimization"),
                "tables_affected": mcp_sug.get("tables_affected", []),
                "columns": mcp_sug.get("columns", [])
            })

        logger.info(f"Generated {len(ai_format_suggestions)} postgres-mcp suggestions")
        return ai_format_suggestions

    except Exception as e:
        logger.warning(f"Failed to fetch postgres-mcp suggestions: {e}", exc_info=True)
        # Don't fail the request if MCP fails
        return []
