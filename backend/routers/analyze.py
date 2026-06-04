from fastapi import APIRouter, HTTPException, Query
from ..deps import resolve_agent
from ..schemas import ExplainRequest, HypoIndexRequest, Recommendation
from ..services.advisor import index_advice_pg, rewrite_advice
from ..services.ai_client import LLMClient
from ..services.ai_suggest import ai_suggestions_for_sql_pg
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["analyze"])

@router.get("/{ds_id}/schema")
def get_schema(ds_id: str):
    agent = resolve_agent(ds_id)
    return agent.get_schema()

@router.get("/{ds_id}/top")
def top_queries(ds_id: str, limit: int = Query(20, ge=1, le=100)):
    agent = resolve_agent(ds_id)
    return agent.get_top_queries(limit=limit)

@router.post("/{ds_id}/explain")
def explain(ds_id: str, body: ExplainRequest):
    agent = resolve_agent(ds_id)
    return agent.explain(body.sql, analyze=body.analyze)

@router.post("/{ds_id}/execute")
def execute_query(ds_id: str, body: ExplainRequest):
    """
    Execute a SQL query and return results.
    Supports:
    - SELECT queries: Returns columns and rows
    - DDL statements (CREATE INDEX, CREATE TABLE, etc.): Returns success message
    - DML statements (INSERT, UPDATE, DELETE): Returns affected row count
    """
    agent = resolve_agent(ds_id)

    try:
        conn = agent._conn()

        # Determine database type to handle results properly
        from ..services.postgres_agent import PostgresAgent
        from ..services.mysql_agent import MySQLAgent
        from ..services.sqlserver_agent import SQLServerAgent
        from ..services.oracle_agent import OracleAgent
        from ..services.sqlite_agent import SQLiteAgent

        if isinstance(agent, PostgresAgent):
            # PostgreSQL with psycopg using dict_row factory
            # Note: rows are already dictionaries due to row_factory=dict_row
            with conn.cursor() as cur:
                cur.execute(body.sql)

                # Check if query returns rows (SELECT, etc.)
                if cur.description:
                    # Query returns data - rows are already dicts from dict_row factory
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()  # Already list of dicts!

                    return {
                        "columns": columns,
                        "rows": rows,  # No conversion needed - already dicts
                        "row_count": len(rows),
                        "status": "success"
                    }
                else:
                    # DDL/DML statement (CREATE, INSERT, UPDATE, DELETE, etc.)
                    # Get affected rows count if available
                    affected_rows = cur.rowcount if hasattr(cur, 'rowcount') and cur.rowcount >= 0 else 0

                    return {
                        "columns": ["status", "message", "affected_rows"],
                        "rows": [{
                            "status": "success",
                            "message": "Statement executed successfully",
                            "affected_rows": affected_rows
                        }],
                        "row_count": 1,
                        "status": "success"
                    }

        elif isinstance(agent, (MySQLAgent, SQLiteAgent)):
            # MySQL with DictCursor, SQLite with Row factory
            # Note: rows are already dictionaries
            with conn.cursor() as cur:
                cur.execute(body.sql)

                # Check if query returns rows
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    # Convert to list of dicts
                    # MySQL DictCursor returns dict, SQLite Row needs dict() conversion
                    if isinstance(agent, MySQLAgent):
                        data = rows  # Already dicts from DictCursor
                    else:  # SQLite
                        data = [dict(row) for row in rows]  # Convert Row to dict

                    conn.close()

                    return {
                        "columns": columns,
                        "rows": data,
                        "row_count": len(data),
                        "status": "success"
                    }
                else:
                    # DDL/DML statement
                    affected_rows = cur.rowcount if hasattr(cur, 'rowcount') and cur.rowcount >= 0 else 0

                    conn.close()

                    return {
                        "columns": ["status", "message", "affected_rows"],
                        "rows": [{
                            "status": "success",
                            "message": "Statement executed successfully",
                            "affected_rows": affected_rows
                        }],
                        "row_count": 1,
                        "status": "success"
                    }

        elif isinstance(agent, (SQLServerAgent, OracleAgent)):
            # SQL Server / Oracle
            with conn.cursor() as cur:
                cur.execute(body.sql)

                # Check if query returns rows
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    # Convert to list of dicts
                    data = []
                    for row in rows:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            value = row[i]
                            # Convert non-serializable types to strings
                            if hasattr(value, 'isoformat'):  # datetime objects
                                row_dict[col] = value.isoformat()
                            elif isinstance(value, (bytes, bytearray)):  # binary data
                                row_dict[col] = value.hex()
                            else:
                                row_dict[col] = value
                        data.append(row_dict)

                    conn.close()

                    return {
                        "columns": columns,
                        "rows": data,
                        "row_count": len(data),
                        "status": "success"
                    }
                else:
                    # DDL/DML statement
                    affected_rows = cur.rowcount if hasattr(cur, 'rowcount') and cur.rowcount >= 0 else 0

                    conn.close()

                    return {
                        "columns": ["status", "message", "affected_rows"],
                        "rows": [{
                            "status": "success",
                            "message": "Statement executed successfully",
                            "affected_rows": affected_rows
                        }],
                        "row_count": 1,
                        "status": "success"
                    }

        else:
            raise HTTPException(400, f"Query execution not supported for {agent.get_db_type()}")

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        import traceback
        traceback.print_exc()

        # Extract detailed error information
        error_type = type(e).__name__
        error_message = str(e)

        # Return error details in a structured format instead of raising HTTPException
        return {
            "columns": ["error_type", "error_message"],
            "rows": [{
                "error_type": error_type,
                "error_message": error_message
            }],
            "row_count": 0,
            "status": "error",
            "error": {
                "type": error_type,
                "message": error_message,
                "details": error_message  # Full error details
            }
        }

@router.get("/{ds_id}/locks")
def locks(ds_id: str):
    agent = resolve_agent(ds_id)
    return agent.locks()

@router.get("/{ds_id}/stats")
def stats(ds_id: str):
    agent = resolve_agent(ds_id)
    return agent.stats()

@router.post("/{ds_id}/advise/index", response_model=list[Recommendation])
def advise_index(ds_id: str, body: ExplainRequest):
    agent = resolve_agent(ds_id)
    if agent.__class__.__name__ != "PostgresAgent":
        raise HTTPException(400, "Index advisor v1 supports Postgres only")
    recs = index_advice_pg(agent, body.sql)
    return [Recommendation(**r) for r in recs]

@router.post("/{ds_id}/advise/rewrite", response_model=list[Recommendation])
def advise_rewrite(ds_id: str, body: ExplainRequest):
    _ = resolve_agent(ds_id)  # not used for now
    recs = rewrite_advice(body.sql)
    return [Recommendation(**r) for r in recs]

@router.post("/{ds_id}/hypo-index")
def hypo_index(ds_id: str, body: HypoIndexRequest):
    agent = resolve_agent(ds_id)
    return agent.hypothetical_index(body.table, body.columns, include=body.include, method=body.method)

@router.post("/{ds_id}/advise/ai")
def advise_ai(ds_id: str, body: ExplainRequest):
    """
    AI-powered query optimization suggestions.
    Supports: All databases (PostgreSQL, MySQL, SQL Server, Oracle, SQLite, MongoDB, Redis, Cassandra)
    """
    logger.info(f"\n{'#'*80}")
    logger.info(f"API ENDPOINT: /analyze/{ds_id}/advise/ai")
    logger.info(f"{'#'*80}")
    logger.info(f"Request Body - SQL: {body.sql}")
    logger.info(f"Request Body - Analyze: {body.analyze}")
    logger.info(f"Data Source ID: {ds_id}")

    agent = resolve_agent(ds_id)
    logger.info(f"Agent Type: {agent.__class__.__name__}")

    # Get database type for context-aware AI suggestions
    db_type = agent.get_db_type().upper()
    logger.info(f"Database Type: {db_type}")

    llm = LLMClient()
    logger.info("LLMClient initialized")

    # Use generic AI suggestions that work for all databases
    from ..services.ai_suggest import ai_suggestions_for_sql_generic
    suggestions = ai_suggestions_for_sql_generic(agent, body.sql, llm)

    logger.info(f"\n{'#'*80}")
    logger.info(f"API RESPONSE - Returning {len(suggestions)} suggestions")
    logger.info(f"{'#'*80}")
    logger.info(json.dumps({"suggestions": suggestions}, indent=2))
    logger.info(f"{'#'*80}\n")

    return {"suggestions": suggestions}

@router.post("/{ds_id}/explain/ai")
def explain_plan_ai(ds_id: str, body: ExplainRequest):
    """
    AI-powered EXPLAIN plan explanation.
    Supports: All databases (PostgreSQL, MySQL, SQL Server, Oracle, SQLite, MongoDB, Redis, Cassandra)
    """
    agent = resolve_agent(ds_id)
    db_type = agent.get_db_type().upper()

    llm = LLMClient()
    explain_result = agent.explain(body.sql, analyze=False)
    plan = explain_result.get("plan") or []

    # Some engines (DuckDB, NoSQL) may not produce a plan or may return an error.
    # Don't ask the LLM to interpret an empty/errored plan — surface a clear note.
    if explain_result.get("error") or not plan:
        reason = explain_result.get("error") or "no execution plan was produced for this engine"
        return {
            "explanation": f"Unable to produce an execution plan for this {db_type} query: {reason}",
            "plan_available": False,
        }

    msg = [
      {"role":"system","content":f"Explain this {db_type} execution plan in clear bullet points. Keep it short and focus on performance implications."},
      {"role":"user","content": json.dumps(plan)}
    ]
    return {"explanation": llm.chat(msg), "plan_available": True}

@router.get("/{ds_id}/indexes")
def get_indexes(ds_id: str, table: str = Query(None, description="Filter by table name")):
    """
    Get all existing indexes, optionally filtered by table.
    Useful for debugging index validation.
    """
    agent = resolve_agent(ds_id)
    from ..services.postgres_agent import PostgresAgent

    if not isinstance(agent, PostgresAgent):
        raise HTTPException(400, "Index checking only supported for PostgreSQL")

    indexes = agent.get_existing_indexes(table)

    return {
        "table_filter": table,
        "count": len(indexes),
        "indexes": indexes
    }

@router.post("/{ds_id}/optimize/database")
def optimize_database(ds_id: str):
    """
    Generate AI-powered optimization suggestions for the entire database.
    Analyzes schema, indexes, and provides general recommendations with executable SQL.
    Supports: All databases (PostgreSQL, MySQL, SQL Server, Oracle, SQLite, MongoDB, Redis, Cassandra)
    """
    agent = resolve_agent(ds_id)
    from ..services.ai_client import LLMClient
    import uuid

    # Support all databases - no restrictions
    db_type = agent.get_db_type()

    try:
        # Get database schema
        schema = agent.get_schema()
        tables = schema.get("tables", {})

        # Get all existing indexes
        all_indexes = agent.get_existing_indexes()

        # Analyze database-level optimization opportunities
        suggestions = []

        # Check for tables without indexes
        tables_without_indexes = []
        for table_name in tables.keys():
            table_short = table_name.split(".")[-1] if "." in table_name else table_name
            table_indexes = [idx for idx in all_indexes if idx['table_name_short'] == table_short]
            if len(table_indexes) <= 1:  # Only primary key
                tables_without_indexes.append(table_short)

        if tables_without_indexes:
            suggestions.append({
                "id": str(uuid.uuid4()),
                "category": "index",
                "severity": "medium",
                "summary": f"{len(tables_without_indexes)} tables have minimal indexing",
                "details": f"Tables: {', '.join(tables_without_indexes[:5])}{'...' if len(tables_without_indexes) > 5 else ''}",
                "recommendation": "Consider adding indexes on frequently queried columns",
                "sql": None,  # No specific SQL, need per-table analysis
                "executable": False
            })

        # AI-powered database analysis
        try:
            llm = LLMClient()

            # Get top 3 largest tables for AI analysis
            table_list = list(tables.keys())[:5]

            # Get database type for context
            db_type = agent.get_db_type().upper()

            prompt = f"""Analyze this {db_type} database and provide optimization suggestions:

Database Statistics:
- Database Type: {db_type}
- Total Tables: {len(tables)}
- Total Indexes: {len(all_indexes)}
- Tables with minimal indexing: {len(tables_without_indexes)}
- Sample tables: {', '.join(table_list)}

Provide 2-3 specific, actionable database-level optimization recommendations.
For each suggestion that involves SQL changes, provide the exact SQL statement compatible with {db_type}.

Format your response as a JSON array of objects with:
- summary: Brief title
- details: Explanation
- sql: Executable SQL statement (if applicable, otherwise null)
- category: "index", "config", "maintenance", or "vacuum"

Example for PostgreSQL:
[
  {{"summary": "Run VACUUM ANALYZE", "details": "Reclaim space and update statistics", "sql": "VACUUM ANALYZE;", "category": "maintenance"}},
  {{"summary": "Add missing indexes", "details": "Analyze query patterns first", "sql": null, "category": "index"}}
]

Example for MySQL:
[
  {{"summary": "Optimize tables", "details": "Defragment and reclaim space", "sql": "OPTIMIZE TABLE table_name;", "category": "maintenance"}},
  {{"summary": "Analyze tables", "details": "Update statistics for query optimizer", "sql": "ANALYZE TABLE table_name;", "category": "maintenance"}}
]"""

            ai_response = llm.chat([
                {"role": "system", "content": f"You are a {db_type} DBA expert. Provide actionable optimization advice with SQL when applicable. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ])

            # Parse AI response
            import json
            try:
                ai_suggestions = json.loads(ai_response.strip())
                if isinstance(ai_suggestions, list):
                    for ai_sug in ai_suggestions:
                        suggestions.append({
                            "id": str(uuid.uuid4()),
                            "category": ai_sug.get("category", "ai"),
                            "severity": "low",
                            "summary": ai_sug.get("summary", "AI Recommendation"),
                            "details": ai_sug.get("details", ""),
                            "recommendation": "Review and apply carefully",
                            "sql": ai_sug.get("sql"),
                            "executable": ai_sug.get("sql") is not None
                        })
            except json.JSONDecodeError:
                logger.warning("AI response was not valid JSON, adding as text")
                suggestions.append({
                    "id": str(uuid.uuid4()),
                    "category": "ai",
                    "severity": "low",
                    "summary": "AI Recommendation",
                    "details": ai_response.strip(),
                    "recommendation": "Review and apply carefully",
                    "sql": None,
                    "executable": False
                })
        except Exception as ai_err:
            logger.error(f"AI suggestion failed: {ai_err}")

        # Get database statistics
        stats = agent.stats()
        suggestions.append({
            "id": str(uuid.uuid4()),
            "category": "info",
            "severity": "low",
            "summary": f"Database size: {stats.get('total_db_size', 0) / (1024**3):.2f} GB",
            "details": f"Active backends: {stats.get('active_backends', 0)}",
            "recommendation": "Monitor database growth and connection usage",
            "sql": None,
            "executable": False
        })

        return {
            "database": ds_id,
            "suggestions": suggestions,
            "table_count": len(tables),
            "index_count": len(all_indexes),
            "timestamp": "now"
        }

    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Optimization failed: {str(e)}")


@router.post("/{ds_id}/optimize/table/{table_name}")
def optimize_table(ds_id: str, table_name: str):
    """
    Generate AI-powered optimization suggestions for a specific table with executable SQL.
    Analyzes indexes, column types, and suggests improvements.
    Supports: All databases (PostgreSQL, MySQL, SQL Server, Oracle, SQLite, MongoDB, Redis, Cassandra)
    """
    agent = resolve_agent(ds_id)
    from ..services.ai_client import LLMClient
    import uuid

    # Support all databases - no restrictions
    db_type = agent.get_db_type()

    try:
        # Get table schema
        schema = agent.get_schema()
        tables = schema.get("tables", {})

        # Find the table (handle schema.table format)
        table_columns = None
        full_table_name = None
        for tname, cols in tables.items():
            if tname.endswith(f".{table_name}") or tname == table_name:
                table_columns = cols
                full_table_name = tname
                break

        if not table_columns:
            raise HTTPException(404, f"Table '{table_name}' not found")

        # Get existing indexes for this table
        table_indexes = agent.get_existing_indexes(table_name)

        suggestions = []

        # Analyze columns
        column_count = len(table_columns)
        indexed_columns = set()
        for idx in table_indexes:
            indexed_columns.update(idx['columns'])

        unindexed_columns = [col['column'] for col in table_columns if col['column'] not in indexed_columns]

        # AI-powered suggestions with SQL
        try:
            llm = LLMClient()

            # Get database type for context
            db_type = agent.get_db_type().upper()

            # Get column details for AI
            column_info = ', '.join([f"{col['column']} ({col['type']})" for col in table_columns[:10]])

            prompt = f"""Analyze this {db_type} table and provide optimization suggestions with SQL:

Database Type: {db_type}
Table: {table_name}
Columns ({column_count}): {column_info}
Existing Indexes ({len(table_indexes)}): {', '.join([idx['index_name'] for idx in table_indexes])}
Unindexed Columns: {', '.join(unindexed_columns[:10])}

Provide 2-4 specific optimization recommendations.
For each suggestion, provide executable SQL compatible with {db_type} if applicable.

Format your response as a JSON array with:
- summary: Brief title
- details: Explanation
- sql: CREATE INDEX or other SQL statement (or null)
- category: "index", "constraint", "type", or "general"

Example:
[
  {{"summary": "Add index on student_id", "details": "Improve foreign key lookups", "sql": "CREATE INDEX idx_{table_name}_student_id ON {table_name} (student_id);", "category": "index"}},
  {{"summary": "Add index on due_date", "details": "Speed up date range queries", "sql": "CREATE INDEX idx_{table_name}_due_date ON {table_name} (due_date);", "category": "index"}}
]"""

            ai_response = llm.chat([
                {"role": "system", "content": f"You are a {db_type} DBA expert. Provide actionable table optimization advice with executable SQL. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ])

            # Parse AI response
            import json
            try:
                # Try to extract JSON from markdown code blocks
                response_text = ai_response.strip()
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                ai_suggestions = json.loads(response_text)
                if isinstance(ai_suggestions, list):
                    for ai_sug in ai_suggestions:
                        sql_statement = ai_sug.get("sql")

                        # Skip if index already exists
                        if sql_statement and "CREATE INDEX" in sql_statement.upper():
                            # Extract columns from CREATE INDEX statement
                            import re
                            match = re.search(r'\(([^)]+)\)', sql_statement)
                            if match:
                                proposed_cols = [c.strip() for c in match.group(1).split(',')]
                                if agent.index_exists(table_name, proposed_cols):
                                    logger.info(f"Skipping AI suggestion - index already exists on {table_name}({', '.join(proposed_cols)})")
                                    continue

                        suggestions.append({
                            "id": str(uuid.uuid4()),
                            "category": ai_sug.get("category", "ai"),
                            "severity": "medium" if sql_statement else "low",
                            "summary": ai_sug.get("summary", "AI Recommendation"),
                            "details": ai_sug.get("details", ""),
                            "recommendation": "Review and apply carefully",
                            "sql": sql_statement,
                            "executable": sql_statement is not None
                        })
            except json.JSONDecodeError as json_err:
                logger.warning(f"AI response was not valid JSON: {json_err}, adding as text")
                suggestions.append({
                    "id": str(uuid.uuid4()),
                    "category": "ai",
                    "severity": "low",
                    "summary": "AI Recommendation",
                    "details": ai_response.strip(),
                    "recommendation": "Review and apply carefully",
                    "sql": None,
                    "executable": False
                })
        except Exception as ai_err:
            logger.error(f"AI suggestion failed: {ai_err}")
            import traceback
            traceback.print_exc()

        # Suggestion: Existing indexes info
        if len(table_indexes) > 0:
            suggestions.append({
                "id": str(uuid.uuid4()),
                "category": "info",
                "severity": "low",
                "summary": f"{len(table_indexes)} existing indexes",
                "details": f"Indexes: {', '.join([idx['index_name'] for idx in table_indexes[:3]])}{'...' if len(table_indexes) > 3 else ''}",
                "recommendation": "Review index usage with EXPLAIN ANALYZE",
                "sql": None,
                "executable": False
            })

        return {
            "table": table_name,
            "full_table_name": full_table_name,
            "suggestions": suggestions,
            "column_count": column_count,
            "index_count": len(table_indexes),
            "timestamp": "now"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Table optimization failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Optimization failed: {str(e)}")


@router.post("/{ds_id}/optimize/apply")
def apply_optimizations(ds_id: str, body: dict):
    """
    Apply selected optimization SQL statements.
    Executes SQL in a transaction and returns results.
    Supports: All SQL databases (PostgreSQL, MySQL, SQL Server, Oracle, SQLite)
    """
    agent = resolve_agent(ds_id)
    from ..services.postgres_agent import PostgresAgent
    from ..services.mysql_agent import MySQLAgent
    from ..services.sqlserver_agent import SQLServerAgent
    from ..services.oracle_agent import OracleAgent
    from ..services.sqlite_agent import SQLiteAgent

    # Support all SQL databases (NoSQL databases don't support arbitrary SQL execution)
    db_type = agent.get_db_type()
    if db_type not in ["postgres", "mysql", "sqlserver", "oracle", "sqlite"]:
        raise HTTPException(400, f"Apply optimization not supported for {db_type} (SQL databases only)")

    sql_statements = body.get("sql_statements", [])
    if not sql_statements:
        raise HTTPException(400, "No SQL statements provided")

    results = []

    # Different databases handle connections differently
    conn = agent._conn()
    try:
        # PostgreSQL uses context manager with transactions
        if isinstance(agent, PostgresAgent):
            with conn.cursor() as cur:
                for sql in sql_statements:
                    try:
                        cur.execute(sql)
                        results.append({
                            "sql": sql,
                            "status": "success",
                            "message": "Executed successfully"
                        })
                        logger.info(f"Successfully executed: {sql}")
                    except Exception as e:
                        results.append({
                            "sql": sql,
                            "status": "error",
                            "message": str(e)
                        })
                        logger.error(f"Failed to execute {sql}: {e}")

        # MySQL/MariaDB uses autocommit by default
        elif isinstance(agent, MySQLAgent):
            with conn.cursor() as cur:
                for sql in sql_statements:
                    try:
                        cur.execute(sql)
                        results.append({
                            "sql": sql,
                            "status": "success",
                            "message": "Executed successfully"
                        })
                        logger.info(f"Successfully executed: {sql}")
                    except Exception as e:
                        results.append({
                            "sql": sql,
                            "status": "error",
                            "message": str(e)
                        })
                        logger.error(f"Failed to execute {sql}: {e}")

        # SQL Server, Oracle, SQLite - use generic approach
        else:
            with conn.cursor() as cur:
                for sql in sql_statements:
                    try:
                        cur.execute(sql)
                        # Try to commit if method exists
                        if hasattr(conn, 'commit'):
                            conn.commit()
                        results.append({
                            "sql": sql,
                            "status": "success",
                            "message": "Executed successfully"
                        })
                        logger.info(f"Successfully executed: {sql}")
                    except Exception as e:
                        # Try to rollback if method exists
                        if hasattr(conn, 'rollback'):
                            try:
                                conn.rollback()
                            except:
                                pass
                        results.append({
                            "sql": sql,
                            "status": "error",
                            "message": str(e)
                        })
                        logger.error(f"Failed to execute {sql}: {e}")
    finally:
        # Close connection for databases that don't use context managers
        if not isinstance(agent, PostgresAgent):
            try:
                conn.close()
            except:
                pass

    return {
        "results": results,
        "success_count": sum(1 for r in results if r["status"] == "success"),
        "error_count": sum(1 for r in results if r["status"] == "error")
    }