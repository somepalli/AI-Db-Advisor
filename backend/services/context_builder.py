"""
Context Builder - Intelligent schema and data context generation for AI
Analyzes user queries to provide relevant table schemas and sample data.
"""
from typing import Dict, Any, List, Optional, Set
import logging
import re
from ..deps import resolve_agent

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds intelligent context for AI chat based on query analysis"""

    def __init__(self, ds_id: str):
        self.ds_id = ds_id
        self.agent = resolve_agent(ds_id)
        self.db_type = self.agent.get_db_type()

    def build_context(
        self,
        user_message: str,
        current_sql: Optional[str] = None,
        max_tables: int = 5,
        include_sample_data: bool = True
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for AI chat.

        Returns:
            {
                "schema_summary": str,
                "relevant_tables": List[str],
                "sample_data": Dict[str, List[Dict]],
                "relationships": List[str],
                "keywords": List[str]
            }
        """
        try:
            # Get full schema
            schema = self.agent.get_schema()
            tables_dict = schema.get("tables", {})

            if not tables_dict:
                return {
                    "schema_summary": "No tables available",
                    "relevant_tables": [],
                    "sample_data": {},
                    "relationships": [],
                    "keywords": []
                }

            # Analyze query to extract keywords and intent
            keywords = self._extract_keywords(user_message, current_sql)

            # Find relevant tables based on keywords
            relevant_tables = self._find_relevant_tables(
                tables_dict,
                keywords,
                max_tables=max_tables
            )

            # Build enhanced schema summary
            schema_summary = self._build_enhanced_schema(
                tables_dict,
                relevant_tables
            )

            # Get sample data for relevant tables
            sample_data = {}
            if include_sample_data:
                sample_data = self._get_sample_data(relevant_tables, limit=3)

            # Detect relationships
            relationships = self._detect_relationships(tables_dict, relevant_tables)

            return {
                "schema_summary": schema_summary,
                "relevant_tables": relevant_tables,
                "sample_data": sample_data,
                "relationships": relationships,
                "keywords": keywords
            }

        except Exception as e:
            logger.error(f"Context building failed: {e}")
            return {
                "schema_summary": "Context unavailable",
                "relevant_tables": [],
                "sample_data": {},
                "relationships": [],
                "keywords": []
            }

    def _extract_keywords(self, user_message: str, current_sql: Optional[str] = None) -> List[str]:
        """Extract keywords from user message and SQL that might be table/column names."""
        keywords = set()

        # Combine message and SQL
        text = user_message.lower()
        if current_sql:
            text += " " + current_sql.lower()

        # Extract potential table/column names (words with underscores or CamelCase)
        # Common patterns: student, enrollment, course, department, etc.
        word_pattern = r'\b([a-z_]+)\b'
        words = re.findall(word_pattern, text)

        # Filter out SQL keywords and common words
        sql_keywords = {
            'select', 'from', 'where', 'join', 'inner', 'left', 'right', 'outer',
            'on', 'and', 'or', 'not', 'in', 'exists', 'between', 'like', 'order',
            'group', 'by', 'having', 'limit', 'offset', 'insert', 'update', 'delete',
            'create', 'alter', 'drop', 'table', 'index', 'view', 'database', 'as',
            'count', 'sum', 'avg', 'min', 'max', 'distinct', 'all', 'any', 'some',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
            'could', 'may', 'might', 'must', 'can', 'show', 'get', 'find', 'list',
            'for', 'to', 'of', 'with', 'by', 'at', 'in', 'on', 'that', 'this',
            'their', 'what', 'which', 'who', 'when', 'how', 'all', 'each', 'every'
        }

        for word in words:
            # Keep words that might be table/column names
            if (len(word) > 2 and
                word not in sql_keywords and
                not word.isdigit()):
                keywords.add(word)

        # Extract year patterns (e.g., "2020", "2024")
        year_pattern = r'\b(20\d{2})\b'
        years = re.findall(year_pattern, user_message)
        keywords.update(years)

        return list(keywords)

    def _find_relevant_tables(
        self,
        tables_dict: Dict[str, List[Dict]],
        keywords: List[str],
        max_tables: int = 5
    ) -> List[str]:
        """
        Find tables most relevant to the query based on keywords.

        Scoring:
        - Table name matches keyword: +10 points
        - Column name matches keyword: +5 points
        - Partial match: +2 points
        """
        scores = {}

        for table_name, columns in tables_dict.items():
            score = 0
            table_lower = table_name.lower()

            # Check table name matches
            for keyword in keywords:
                keyword_lower = keyword.lower()

                # Exact match in table name
                if keyword_lower in table_lower:
                    score += 10

                # Check column names
                for col in columns:
                    col_name = col.get("column", "").lower()

                    # Exact match in column name
                    if keyword_lower == col_name:
                        score += 5
                    # Partial match in column name
                    elif keyword_lower in col_name or col_name in keyword_lower:
                        score += 2

            scores[table_name] = score

        # Sort by score descending
        sorted_tables = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Return top N tables with score > 0, or first N if none match
        relevant = [t[0] for t in sorted_tables if t[1] > 0][:max_tables]

        if not relevant:
            # No matches, return first N tables
            relevant = list(tables_dict.keys())[:max_tables]

        logger.info(f"Relevant tables for keywords {keywords}: {relevant}")
        logger.debug(f"Table scores: {dict(sorted_tables[:10])}")

        return relevant

    def _build_enhanced_schema(
        self,
        tables_dict: Dict[str, List[Dict]],
        relevant_tables: List[str]
    ) -> str:
        """Build enhanced schema summary with types and constraints."""
        lines = []

        for table_name in relevant_tables:
            if table_name not in tables_dict:
                continue

            columns = tables_dict[table_name]

            lines.append(f"\n{table_name}:")

            for col in columns[:15]:  # Show up to 15 columns
                col_name = col.get("column", "?")
                col_type = col.get("type", "?")
                nullable = col.get("nullable", "?")

                # Format: column_name (type) [NOT NULL]
                null_str = "" if nullable == "YES" else " NOT NULL"
                lines.append(f"  - {col_name} ({col_type}){null_str}")

            if len(columns) > 15:
                lines.append(f"  ... and {len(columns) - 15} more columns")

        # Add summary
        other_count = len(tables_dict) - len(relevant_tables)
        if other_count > 0:
            other_tables = [t for t in tables_dict.keys() if t not in relevant_tables]
            lines.append(f"\nOther tables available ({other_count}): {', '.join(other_tables[:10])}")

        return "\n".join(lines)

    def _get_sample_data(self, table_names: List[str], limit: int = 3) -> Dict[str, List[Dict]]:
        """Fetch sample data from relevant tables."""
        sample_data = {}

        for table_name in table_names[:3]:  # Max 3 tables to avoid too much data
            try:
                # Build SELECT query
                if self.db_type == "mongodb":
                    # MongoDB: use find()
                    conn = self.agent._conn()
                    db = conn[table_name.split('.')[0]]
                    collection = db[table_name.split('.')[-1]]
                    cursor = collection.find().limit(limit)
                    rows = list(cursor)
                    # Convert ObjectId to string
                    for row in rows:
                        if '_id' in row:
                            row['_id'] = str(row['_id'])
                    sample_data[table_name] = rows
                elif self.db_type == "redis":
                    # Redis: skip sample data
                    continue
                else:
                    # SQL databases
                    conn = self.agent._conn()
                    cursor = conn.cursor()

                    # Get sample rows
                    query = f"SELECT * FROM {table_name} LIMIT {limit}"
                    cursor.execute(query)

                    # Fetch column names
                    if hasattr(cursor, 'description'):
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()

                        # Convert to list of dicts
                        sample_data[table_name] = [
                            dict(zip(columns, row)) for row in rows
                        ]

                    cursor.close()
                    conn.close()

                logger.info(f"Fetched {len(sample_data.get(table_name, []))} sample rows from {table_name}")

            except Exception as e:
                logger.warning(f"Failed to fetch sample data from {table_name}: {e}")
                # Continue with other tables
                continue

        return sample_data

    def _detect_relationships(
        self,
        tables_dict: Dict[str, List[Dict]],
        relevant_tables: List[str]
    ) -> List[str]:
        """
        Detect potential relationships between tables.

        Heuristics:
        - Columns ending with _id likely reference other tables
        - Column names matching table names indicate FK relationships
        """
        relationships = []

        for table_name in relevant_tables:
            if table_name not in tables_dict:
                continue

            columns = tables_dict[table_name]

            for col in columns:
                col_name = col.get("column", "").lower()

                # Check for _id pattern
                if col_name.endswith('_id'):
                    # Extract potential referenced table
                    potential_table = col_name[:-3]  # Remove '_id'

                    # Check if a table with similar name exists
                    for other_table in tables_dict.keys():
                        other_table_lower = other_table.lower().split('.')[-1]

                        # Check if table name matches (singular/plural handling)
                        if (potential_table in other_table_lower or
                            other_table_lower in potential_table or
                            potential_table + 's' == other_table_lower or
                            potential_table == other_table_lower + 's'):

                            relationships.append(
                                f"{table_name}.{col_name} → {other_table}"
                            )
                            break

        return relationships


def build_ai_context(
    ds_id: str,
    user_message: str,
    current_sql: Optional[str] = None,
    max_tables: int = 5,
    include_sample_data: bool = True
) -> str:
    """
    Build comprehensive AI context string.

    Returns formatted string with:
    - Relevant table schemas with types
    - Sample data from tables
    - Detected relationships
    """
    builder = ContextBuilder(ds_id)
    context = builder.build_context(
        user_message,
        current_sql,
        max_tables,
        include_sample_data
    )

    lines = []

    # Schema
    lines.append("=== RELEVANT TABLES ===")
    lines.append(context["schema_summary"])

    # Relationships
    if context["relationships"]:
        lines.append("\n=== RELATIONSHIPS ===")
        for rel in context["relationships"]:
            lines.append(f"  {rel}")

    # Sample Data
    if context["sample_data"]:
        lines.append("\n=== SAMPLE DATA ===")
        for table_name, rows in context["sample_data"].items():
            lines.append(f"\n{table_name} (sample):")
            for i, row in enumerate(rows, 1):
                # Format row data
                row_str = ", ".join([f"{k}={v}" for k, v in list(row.items())[:5]])
                lines.append(f"  {i}. {row_str}")

    return "\n".join(lines)
