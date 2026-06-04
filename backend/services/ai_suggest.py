# app/services/ai_suggest.py
from __future__ import annotations
from typing import Dict, Any, List
import json
import logging
from .ai_client import LLMClient
from .postgres_agent import PostgresAgent
from .base_agent import BaseAgent
from ..utils.plan_diff import summarize_diff

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """You are a senior database performance engineer specializing in PostgreSQL optimization.

Analyze the provided SQL query and suggest up to 3 concrete performance improvements.

CRITICAL: You MUST respond with ONLY valid JSON in this EXACT format:
{
  "suggestions": [
    {
      "type": "index",
      "summary": "Brief description of the suggestion",
      "rationale": "Detailed explanation of why this helps",
      "risk": "low",
      "index": {
        "table": "table_name",
        "columns": ["col1", "col2"],
        "include": ["col3"]
      }
    },
    {
      "type": "rewrite",
      "summary": "Brief description of the rewrite",
      "rationale": "Why this rewrite improves performance",
      "risk": "low",
      "new_sql": "SELECT ... (the rewritten query)"
    },
    {
      "type": "note",
      "summary": "General advice or observation",
      "rationale": "Explanation of the advice",
      "risk": "low"
    }
  ]
}

Rules:
- ALWAYS return valid JSON starting with { and ending with }
- ALWAYS include the "suggestions" key as the root array
- Each suggestion MUST have: type, summary, rationale, risk
- For type="index": include "index" object with table, columns, include arrays
- For type="rewrite": include "new_sql" with the rewritten query
- For type="note": just provide summary and rationale
- risk can be: "low", "medium", or "high"
- Maximum 3 suggestions
- Keep semantics identical for rewrites
- Prefer composite indexes with equality predicates first

DO NOT include any text before or after the JSON object."""

USER_TEMPLATE = """Engine: {engine}
Schema sample (partial): {schema_sample}
SQL:
{sql}
Plan (top node excerpt):
{plan_excerpt}
Constraints:
- Keep semantics identical if proposing rewrites.
- Prefer composite index ordering: equality predicates first, then range, then order/group/order-by.
- Avoid vendor-specific hints unless engine is that vendor.
- Maximum 3 suggestions.
Return ONLY JSON.
"""

def _plan_excerpt(plan_json: Any, limit_keys=("Node Type","Total Cost","Plan Rows","Filter","Index Cond","Hash Cond","Merge Cond")) -> str:
    try:
        plan = plan_json[0]["Plan"]
        def pick(d, keys):
            return {k: d.get(k) for k in keys if k in d}
        return json.dumps(pick(plan, limit_keys))
    except Exception:
        return "(unavailable)"

def _schema_sample(tables: Dict[str, Any], max_tables=3, max_cols=6) -> Dict[str, Any]:
    out = {}
    for i, (t, cols) in enumerate(tables.items()):
        if i >= max_tables: break
        out[t] = cols[:max_cols]
    return out

def ai_suggestions_for_sql_pg(agent: PostgresAgent, sql: str, llm: LLMClient) -> List[Dict[str, Any]]:
    logger.info("="*80)
    logger.info("AI SUGGESTIONS - START")
    logger.info("="*80)
    logger.info(f"Input SQL:\n{sql}")

    # 1) Collect minimal context
    schema = agent.get_schema()
    before = agent.explain(sql, analyze=False)
    schema_sample = _schema_sample(schema.get("tables", {}))

    logger.info(f"\nSchema Sample:\n{json.dumps(schema_sample, indent=2)}")
    logger.info(f"\nPlan Excerpt:\n{_plan_excerpt(before['plan'])}")

    # 2) Ask LLM for JSON suggestions
    user_content = USER_TEMPLATE.format(
        engine="PostgreSQL",
        schema_sample=json.dumps(schema_sample),
        sql=sql,
        plan_excerpt=_plan_excerpt(before["plan"])
    )

    messages = [
        {"role":"system","content": SYSTEM_PROMPT},
        {"role":"user","content": user_content}
    ]

    logger.info(f"\n{'='*80}")
    logger.info("LLM INPUT - System Prompt:")
    logger.info(f"{'='*80}")
    logger.info(SYSTEM_PROMPT)

    logger.info(f"\n{'='*80}")
    logger.info("LLM INPUT - User Content:")
    logger.info(f"{'='*80}")
    logger.info(user_content)

    try:
        resp = llm.chat(messages, json_response=True)

        logger.info(f"\n{'='*80}")
        logger.info("LLM RESPONSE (RAW):")
        logger.info(f"{'='*80}")
        logger.info(f"Type: {type(resp)}")
        logger.info(f"Content:\n{json.dumps(resp, indent=2) if not isinstance(resp, str) else resp}")

        # Handle different response formats
        if isinstance(resp, str):
            # model didn't return valid JSON; wrap as a note
            logger.warning("LLM returned a string instead of JSON object")
            suggestions = [{"type":"note","summary":"LLM returned text; enable json mode or try another model.","rationale":resp[:500],"risk":"low"}]
        elif isinstance(resp, dict):
            # Expected format: {"suggestions": [...]}
            suggestions = resp.get("suggestions", [])
            if not suggestions:
                logger.warning(f"No 'suggestions' key found in response. Keys: {list(resp.keys())}")
                # Maybe the LLM returned suggestions directly in different format
                # Try to convert if it's a different structure
                if isinstance(resp, list):
                    # If it's directly a list, wrap it
                    suggestions = resp
                else:
                    # Return empty or create a note
                    suggestions = [{"type":"note","summary":"Unexpected LLM response format","rationale":f"Response keys: {list(resp.keys())}","risk":"low"}]
        elif isinstance(resp, list):
            # Sometimes LLM returns array directly instead of {"suggestions": [...]}
            logger.warning("LLM returned array directly instead of object with 'suggestions' key")
            suggestions = resp
        else:
            logger.error(f"Unexpected response type: {type(resp)}")
            suggestions = [{"type":"note","summary":"Unexpected LLM response type","rationale":f"Got type: {type(resp)}","risk":"low"}]

        logger.info(f"\n{'='*80}")
        logger.info(f"EXTRACTED SUGGESTIONS ({len(suggestions)} items):")
        logger.info(f"{'='*80}")
        logger.info(json.dumps(suggestions, indent=2))

        # Validate suggestion structure
        validated_suggestions = []
        for idx, sug in enumerate(suggestions):
            if not isinstance(sug, dict):
                logger.warning(f"Suggestion {idx} is not a dict: {type(sug)}")
                continue

            # Ensure required fields exist
            if "type" not in sug:
                logger.warning(f"Suggestion {idx} missing 'type' field")
                sug["type"] = "note"
            if "summary" not in sug:
                logger.warning(f"Suggestion {idx} missing 'summary' field")
                sug["summary"] = "Suggestion missing summary"

            validated_suggestions.append(sug)

        suggestions = validated_suggestions

        if not suggestions:
            logger.warning("No valid suggestions after validation")
            suggestions = [{"type":"note","summary":"No valid suggestions generated","rationale":"LLM response could not be parsed into valid suggestions","risk":"low"}]

    except Exception as e:
        logger.error(f"\n{'='*80}")
        logger.error("LLM ERROR:")
        logger.error(f"{'='*80}")
        logger.error(f"Exception: {str(e)}")
        logger.error(f"Exception Type: {type(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # LLM offline → graceful note
        return [{"type":"note","summary":"AI model unreachable; falling back to heuristic advisor.","rationale":str(e),"risk":"low"}]

    # 3) Validate rewrites and indexes (quick EXPLAIN / HypoPG if available)
    logger.info(f"\n{'='*80}")
    logger.info("VALIDATION PHASE - START")
    logger.info(f"{'='*80}")

    validated: List[Dict[str, Any]] = []
    for idx, s in enumerate(suggestions[:3]):
        logger.info(f"\nValidating suggestion {idx + 1}/{len(suggestions[:3])}: {s.get('type')}")
        s_type = s.get("type")

        if s_type == "rewrite" and s.get("new_sql"):
            logger.info(f"  Rewrite SQL: {s.get('new_sql')}")
            try:
                after = agent.explain(s["new_sql"], analyze=False)
                diff = summarize_diff(before["plan"], after["plan"])
                gain = f"Plan cost ↓ {diff.get('cost_delta_pct','?')}%, rows ↓ {diff.get('rows_delta_pct','?')}%"
                s["validated"] = True if diff else False
                s["expected_gain"] = gain if diff else "Unknown"
                logger.info(f"  Validation result: {s['validated']}, Gain: {gain}")
            except Exception as e:
                logger.error(f"  Validation failed: {str(e)}")
                s["validated"] = False
                s["expected_gain"] = "Explain failed; review manually"
            validated.append(s)

        elif s_type == "index" and s.get("index"):
            idx_info = s["index"]
            table = idx_info.get("table")
            cols  = idx_info.get("columns") or []
            include = idx_info.get("include") or []
            logger.info(f"  Index on {table}({', '.join(cols)}) INCLUDE ({', '.join(include)})")
            try:
                hypo = agent.hypothetical_index(table, cols, include=include, method="btree")
                after = agent.plan_with_hypo(sql, hypo.get("hypo_stmt"))
                diff = summarize_diff(before["plan"], after["plan"])
                s["validated"] = after.get("validated", False)
                if diff:
                    s["expected_gain"] = f"Plan cost ↓ {diff.get('cost_delta_pct','?')}%, rows ↓ {diff.get('rows_delta_pct','?')}%"
                if s.get("validated"):
                    s["sql_fix"] = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_{table}_{'_'.join(cols)} ON {table} ({', '.join(cols)})" + (f" INCLUDE ({', '.join(include)});" if include else ";")
                else:
                    s["sql_fix"] = f"-- HypoPG unavailable; validate on staging:\nCREATE INDEX idx_ai_{table}_{'_'.join(cols)} ON {table} ({', '.join(cols)})" + (f" INCLUDE ({', '.join(include)});" if include else ";")
                logger.info(f"  Validation result: {s.get('validated')}, Gain: {s.get('expected_gain')}")
            except Exception as e:
                logger.error(f"  Index validation failed: {str(e)}")
                s["validated"] = False
                s["expected_gain"] = "Index validation failed; review on staging"
            validated.append(s)

        else:
            # notes / general advice
            logger.info(f"  Note/general advice - no validation needed")
            validated.append(s)

    logger.info(f"\n{'='*80}")
    logger.info("FINAL VALIDATED SUGGESTIONS:")
    logger.info(f"{'='*80}")
    logger.info(json.dumps(validated, indent=2))
    logger.info(f"{'='*80}")
    logger.info("AI SUGGESTIONS - END")
    logger.info(f"{'='*80}\n")

    return validated


def ai_suggestions_for_sql_generic(agent: BaseAgent, sql: str, llm: LLMClient) -> List[Dict[str, Any]]:
    """
    Generic AI suggestions for any database type.
    Works for: PostgreSQL, MySQL, SQL Server, Oracle, SQLite, MongoDB, Redis, Cassandra
    """
    logger.info("="*80)
    logger.info("AI SUGGESTIONS (GENERIC) - START")
    logger.info("="*80)

    db_type = agent.get_db_type().upper()
    logger.info(f"Database Type: {db_type}")
    logger.info(f"Input SQL/Query:\n{sql}")

    # 1) Collect minimal context
    try:
        schema = agent.get_schema()
        all_tables = schema.get("tables", {})
        schema_sample = _schema_sample(all_tables)
    except Exception as e:
        logger.warning(f"Schema extraction failed: {e}")
        schema_sample = {}
        all_tables = {}

    # Validate tables and columns in the SQL query
    missing_tables = []
    missing_columns = []
    validation_warnings = []

    try:
        # Extract table names and column names from SQL using basic parsing
        from ..utils.sql_parse import extract_predicates

        # Get all table names from schema (handle schema.table format)
        existing_tables = set()
        table_columns_map = {}  # Map of table -> list of columns

        for full_table_name, columns in all_tables.items():
            # Extract short table name (remove schema prefix)
            table_short = full_table_name.split(".")[-1] if "." in full_table_name else full_table_name
            existing_tables.add(table_short.lower())

            # Map columns for this table
            table_columns_map[table_short.lower()] = [col.get('column', '').lower() for col in columns]

        # Simple SQL parsing to find table names (FROM, JOIN clauses)
        import re
        sql_upper = sql.upper()

        # Extract tables from FROM and JOIN clauses
        from_pattern = r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_\.]*)'
        join_pattern = r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_\.]*)'

        tables_in_query = set()
        for match in re.finditer(from_pattern, sql_upper, re.IGNORECASE):
            table_name = match.group(1).strip().lower()
            # Remove schema prefix if present
            table_short = table_name.split(".")[-1] if "." in table_name else table_name
            tables_in_query.add(table_short)

        for match in re.finditer(join_pattern, sql_upper, re.IGNORECASE):
            table_name = match.group(1).strip().lower()
            table_short = table_name.split(".")[-1] if "." in table_name else table_name
            tables_in_query.add(table_short)

        # Check for missing tables
        for table in tables_in_query:
            if table not in existing_tables and not table.startswith('('):  # Exclude subqueries
                missing_tables.append(table)
                logger.warning(f"  ⚠ Table '{table}' not found in schema!")

        # Extract column references (basic pattern matching)
        # This is a simplified approach - real SQL parsing is complex
        column_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)'

        for match in re.finditer(column_pattern, sql, re.IGNORECASE):
            table_alias = match.group(1).strip().lower()
            column_name = match.group(2).strip().lower()

            # Try to resolve table alias to actual table
            # For now, check if column exists in any table
            found = False
            for table, cols in table_columns_map.items():
                if column_name in cols:
                    found = True
                    break

            if not found and column_name not in ['*', 'count', 'sum', 'avg', 'min', 'max']:  # Exclude aggregates
                # Don't add duplicates
                if column_name not in [c for t, c in missing_columns]:
                    missing_columns.append((table_alias, column_name))
                    logger.warning(f"  ⚠ Column '{table_alias}.{column_name}' not found in schema!")

        # Create validation warnings for AI to include in suggestions
        if missing_tables:
            validation_warnings.append({
                "type": "missing_table",
                "tables": missing_tables,
                "message": f"Tables not found in schema: {', '.join(missing_tables)}"
            })

        if missing_columns:
            validation_warnings.append({
                "type": "missing_column",
                "columns": [f"{t}.{c}" for t, c in missing_columns],
                "message": f"Columns not found in schema: {', '.join([f'{t}.{c}' for t, c in missing_columns])}"
            })

    except Exception as e:
        logger.warning(f"SQL validation failed: {e}")
        import traceback
        logger.warning(traceback.format_exc())

    # Get EXPLAIN plan if available
    plan_excerpt = "(unavailable)"
    try:
        before = agent.explain(sql, analyze=False)
        # Different databases have different plan formats
        if db_type == "POSTGRES":
            plan_excerpt = _plan_excerpt(before.get('plan', []))
        elif db_type in ["MYSQL", "MARIADB"]:
            # Extract MySQL-specific plan details
            plan = before.get('plan', {})
            excerpt_parts = []

            # Check for filesort/temporary table
            def extract_mysql_info(node, depth=0):
                if isinstance(node, dict):
                    if node.get('using_filesort'):
                        excerpt_parts.append(f"  {'  '*depth}⚠ Using filesort (slow sorting without index)")
                    if node.get('using_temporary'):
                        excerpt_parts.append(f"  {'  '*depth}⚠ Using temporary table")
                    if 'table' in node:
                        table_name = node['table'].get('table_name', 'unknown')
                        access_type = node['table'].get('access_type', 'unknown')
                        key = node['table'].get('key', 'none')
                        rows = node['table'].get('rows_examined_per_scan', '?')
                        excerpt_parts.append(f"  {'  '*depth}Table: {table_name}, Access: {access_type}, Key: {key}, Rows: {rows}")
                    for k, v in node.items():
                        extract_mysql_info(v, depth + 1)
                elif isinstance(node, list):
                    for item in node:
                        extract_mysql_info(item, depth)

            extract_mysql_info(plan)
            plan_excerpt = "\n".join(excerpt_parts) if excerpt_parts else json.dumps(plan)[:500]
        else:
            plan_excerpt = json.dumps(before.get('plan', {}))[:500]
    except Exception as e:
        logger.warning(f"EXPLAIN plan extraction failed: {e}")

    logger.info(f"\nSchema Sample:\n{json.dumps(schema_sample, indent=2)}")
    logger.info(f"\nPlan Excerpt:\n{plan_excerpt}")

    # 2) Create database-specific system prompt
    system_prompt = f"""You are a senior database performance engineer specializing in {db_type} optimization.

Analyze the provided SQL query and suggest up to 3 concrete performance improvements.

CRITICAL: You MUST respond with ONLY valid JSON in this EXACT format:
{{
  "suggestions": [
    {{
      "type": "error",
      "summary": "SQL Error: Missing table or column",
      "rationale": "The query references tables/columns that don't exist in the schema",
      "risk": "high",
      "fix_suggestions": ["Check table name spelling", "Verify column exists"]
    }},
    {{
      "type": "index",
      "summary": "Brief description of the suggestion",
      "rationale": "Detailed explanation of why this helps",
      "risk": "low",
      "index": {{
        "table": "table_name",
        "columns": ["col1", "col2"]
      }}
    }},
    {{
      "type": "rewrite",
      "summary": "Brief description of the rewrite",
      "rationale": "Why this rewrite improves performance",
      "risk": "low",
      "new_sql": "SELECT ... (the rewritten query)"
    }},
    {{
      "type": "note",
      "summary": "General observation or best practice (not actionable)",
      "rationale": "Educational information or context",
      "risk": "low"
    }}
  ]
}}

Rules:
- ALWAYS return valid JSON starting with {{ and ending with }}
- ALWAYS include the "suggestions" key as the root array
- Each suggestion MUST have: type, summary, rationale, risk
- For type="error": Use when SQL has errors (missing tables/columns), include fix_suggestions array
- For type="index": MUST include "index" object with table and columns (actionable)
- For type="rewrite": MUST include "new_sql" with the complete rewritten query (actionable)
- For type="note": Use ONLY for general observations, NOT for actionable suggestions
- If suggesting an index, use type="index" and provide the index details, NOT type="note"
- If suggesting a query change, use type="rewrite" and provide new_sql, NOT type="note"
- risk can be: "low", "medium", or "high" (use "high" for errors)
- Maximum 3 suggestions (but errors should always be included first)
- Keep semantics identical for rewrites
- Use {db_type}-specific syntax and best practices
- Prioritize error suggestions, then actionable suggestions (index/rewrite), then notes

CORRECT Examples:
✓ If the query has WHERE student_id=1 ORDER BY due_date and filesort is detected:
  {{"type": "index", "summary": "Create composite index on (student_id, due_date)", "rationale": "Eliminates filesort by covering both filtering and sorting", "risk": "low", "index": {{"table": "fees", "columns": ["student_id", "due_date"]}}}}

✓ If you want to suggest adding an index on column 'due_date':
  {{"type": "index", "summary": "Add index on due_date", "rationale": "Improves sorting", "risk": "low", "index": {{"table": "fees", "columns": ["due_date"]}}}}

✗ WRONG - Don't do this:
  {{"type": "note", "summary": "Consider creating an index on due_date", ...}}

✓ If you want to suggest a query rewrite:
  {{"type": "rewrite", "summary": "Optimize query", "rationale": "...", "risk": "low", "new_sql": "SELECT col1 FROM ..."}}

PRIORITY: Always suggest composite indexes (type="index") for queries with filesort/temporary table issues BEFORE suggesting rewrites.

DO NOT include any text before or after the JSON object."""

    # 3) Ask LLM for JSON suggestions
    validation_msg = ""
    if validation_warnings:
        validation_msg = "\n\n⚠️ VALIDATION WARNINGS:\n"
        for warning in validation_warnings:
            validation_msg += f"- {warning['message']}\n"
        validation_msg += "\nIMPORTANT: Include these validation errors as a separate 'error' type suggestion with suggestions to fix!\n"

    user_content = f"""Database Engine: {db_type}
Schema sample (partial): {json.dumps(schema_sample)}
SQL:
{sql}
Plan excerpt:
{plan_excerpt}{validation_msg}

Constraints:
- Keep semantics identical if proposing rewrites.
- Use {db_type}-specific syntax and features.
- For indexes, prefer columns used in WHERE, JOIN ON, and ORDER BY clauses.
- Maximum 3 suggestions.
- IMPORTANT: If you want to suggest creating an index, use type="index" with the index object, NOT type="note"
- IMPORTANT: For MySQL, avoid LIMIT in subqueries (not supported in older versions)
- IMPORTANT: For rewrites, keep the query simple and functionally equivalent
- Only use type="note" for general observations that don't have specific SQL actions
- IMPORTANT: If the plan shows "using_filesort" or "Using temporary", you MUST suggest a composite index using type="index"
- IMPORTANT: Prioritize index suggestions over rewrites when filesort/temporary tables are present
- CRITICAL: If there are validation warnings about missing tables or columns, include them as type="error" suggestions first!

Return ONLY JSON."""

    messages = [
        {"role":"system","content": system_prompt},
        {"role":"user","content": user_content}
    ]

    logger.info(f"\n{'='*80}")
    logger.info("LLM INPUT - System Prompt:")
    logger.info(f"{'='*80}")
    logger.info(system_prompt[:500] + "...")

    logger.info(f"\n{'='*80}")
    logger.info("LLM INPUT - User Content:")
    logger.info(f"{'='*80}")
    logger.info(user_content)

    try:
        resp = llm.chat(messages, json_response=True)

        logger.info(f"\n{'='*80}")
        logger.info("LLM RESPONSE (RAW):")
        logger.info(f"{'='*80}")
        logger.info(f"Type: {type(resp)}")
        logger.info(f"Content:\n{json.dumps(resp, indent=2) if not isinstance(resp, str) else resp}")

        # Handle different response formats
        if isinstance(resp, str):
            logger.warning("LLM returned a string instead of JSON object")
            suggestions = [{"type":"note","summary":"LLM returned text","rationale":resp[:500],"risk":"low"}]
        elif isinstance(resp, dict):
            suggestions = resp.get("suggestions", [])
            if not suggestions:
                logger.warning(f"No 'suggestions' key found. Keys: {list(resp.keys())}")
                suggestions = [{"type":"note","summary":"Unexpected LLM response format","rationale":f"Response keys: {list(resp.keys())}","risk":"low"}]
        elif isinstance(resp, list):
            logger.warning("LLM returned array directly")
            suggestions = resp
        else:
            logger.error(f"Unexpected response type: {type(resp)}")
            suggestions = [{"type":"note","summary":"Unexpected LLM response type","rationale":f"Got type: {type(resp)}","risk":"low"}]

        logger.info(f"\n{'='*80}")
        logger.info(f"EXTRACTED SUGGESTIONS ({len(suggestions)} items):")
        logger.info(f"{'='*80}")
        logger.info(json.dumps(suggestions, indent=2))

        # Validate suggestion structure
        validated_suggestions = []
        for idx, sug in enumerate(suggestions):
            if not isinstance(sug, dict):
                logger.warning(f"Suggestion {idx} is not a dict: {type(sug)}")
                continue

            # Ensure required fields
            if "type" not in sug:
                sug["type"] = "note"
            if "summary" not in sug:
                sug["summary"] = "Suggestion missing summary"

            # Add SQL fix for index suggestions
            if sug.get("type") == "index" and sug.get("index"):
                idx_info = sug["index"]
                table = idx_info.get("table")
                cols = idx_info.get("columns", [])

                if not table or not cols:
                    logger.warning(f"  Skipping index suggestion - missing table or columns: {sug}")
                    continue

                # Check if index already exists
                try:
                    if agent.index_exists(table, cols):
                        logger.info(f"  Skipping - index already exists on {table}({', '.join(cols)})")
                        continue
                except Exception as e:
                    logger.warning(f"  Index check failed: {e}")

                # Generate SQL fix based on database type
                if db_type == "POSTGRES":
                    sug["sql_fix"] = f"CREATE INDEX CONCURRENTLY idx_{table}_{'_'.join(cols)} ON {table} ({', '.join(cols)});"
                elif db_type in ["MYSQL", "MARIADB"]:
                    sug["sql_fix"] = f"CREATE INDEX idx_{table}_{'_'.join(cols)} ON {table} ({', '.join(cols)});"
                elif db_type == "SQLSERVER":
                    sug["sql_fix"] = f"CREATE INDEX idx_{table}_{'_'.join(cols)} ON {table} ({', '.join(cols)});"
                elif db_type == "ORACLE":
                    sug["sql_fix"] = f"CREATE INDEX idx_{table}_{'_'.join(cols)} ON {table} ({', '.join(cols)});"
                elif db_type == "SQLITE":
                    sug["sql_fix"] = f"CREATE INDEX idx_{table}_{'_'.join(cols)} ON {table} ({', '.join(cols)});"
                else:
                    sug["sql_fix"] = f"-- Index suggestion for {table}({', '.join(cols)})"

                sug["validated"] = False  # Generic path doesn't validate with HypoPG
                sug["expected_gain"] = "Validation not available for this database type"

            # Add info for rewrite suggestions
            elif sug.get("type") == "rewrite" and sug.get("new_sql"):
                # Try to validate the rewrite by explaining it
                try:
                    new_sql = sug.get("new_sql")
                    logger.info(f"  Validating rewrite SQL: {new_sql[:100]}...")

                    # Try to EXPLAIN the new SQL to check if it's valid
                    explain_result = agent.explain(new_sql, analyze=False)
                    if explain_result:
                        sug["validated"] = True
                        sug["expected_gain"] = "Rewrite validated successfully"
                        logger.info(f"  Rewrite SQL is valid!")
                    else:
                        sug["validated"] = False
                        sug["expected_gain"] = "Could not validate rewrite"
                except Exception as e:
                    logger.warning(f"  Rewrite validation failed: {e}")
                    # If validation fails, check for common MySQL incompatibilities
                    new_sql_lower = sug.get("new_sql", "").lower()
                    if "limit" in new_sql_lower and "in (" in new_sql_lower:
                        logger.error(f"  Rewrite uses LIMIT in subquery - not supported in MySQL!")
                        # Skip this suggestion - it won't work
                        continue

                    sug["validated"] = False
                    sug["expected_gain"] = f"Validation failed: {str(e)[:100]}"

            # Skip pure note suggestions that don't have actionable content
            elif sug.get("type") == "note":
                # Check if note is actually suggesting an index (AI mistake)
                summary = sug.get("summary", "").lower()
                rationale = sug.get("rationale", "").lower()

                # Keywords that indicate this should be an index suggestion
                index_keywords = ["create index", "creating index", "add index", "adding index", "composite index", "index on"]

                if any(keyword in summary or keyword in rationale for keyword in index_keywords):
                    logger.warning(f"  Note appears to suggest an index - this should be type='index' instead!")
                    logger.warning(f"  Summary: {summary[:100]}")
                    # Skip this note - it's a malformed suggestion
                    continue

                # Notes are informational only - no SQL to execute
                logger.info(f"  Note suggestion (advisory only): {sug.get('summary', '')[:50]}...")

            validated_suggestions.append(sug)

        suggestions = validated_suggestions

        # Inject validation warnings as error suggestions if not already present
        if validation_warnings:
            # Check if AI already included error suggestions
            has_error_suggestions = any(sug.get('type') == 'error' for sug in suggestions)

            if not has_error_suggestions:
                logger.info("AI did not include validation warnings - injecting them")
                # Add validation errors at the beginning
                for warning in validation_warnings:
                    error_sug = {
                        "type": "error",
                        "summary": f"SQL Error: {warning['type'].replace('_', ' ').title()}",
                        "rationale": warning['message'],
                        "risk": "high",
                        "fix_suggestions": []
                    }

                    if warning['type'] == 'missing_table':
                        error_sug['fix_suggestions'] = [
                            f"Verify table names: {', '.join(warning['tables'])}",
                            "Check if schema prefix is needed",
                            "Ensure tables exist in the database"
                        ]
                    elif warning['type'] == 'missing_column':
                        error_sug['fix_suggestions'] = [
                            f"Verify column names: {', '.join(warning['columns'])}",
                            "Check table aliases match actual tables",
                            "Ensure columns exist in their respective tables"
                        ]

                    # Insert at beginning
                    suggestions.insert(0, error_sug)

        if not suggestions:
            logger.warning("No valid suggestions after validation")
            suggestions = [{"type":"note","summary":"No valid suggestions generated","rationale":"LLM response could not be parsed","risk":"low"}]

    except Exception as e:
        logger.error(f"\n{'='*80}")
        logger.error("LLM ERROR:")
        logger.error(f"{'='*80}")
        logger.error(f"Exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return [{"type":"note","summary":"AI model unreachable","rationale":str(e),"risk":"low"}]

    logger.info(f"\n{'='*80}")
    logger.info("FINAL SUGGESTIONS:")
    logger.info(f"{'='*80}")
    logger.info(json.dumps(suggestions, indent=2))
    logger.info(f"{'='*80}")
    logger.info("AI SUGGESTIONS (GENERIC) - END")
    logger.info(f"{'='*80}\n")

    return suggestions
