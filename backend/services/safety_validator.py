"""
Safety Validator - Risk Assessment and Validation for MCP Suggestions

Analyzes MCP-generated suggestions for safety risks before user approval.
"""
from typing import Dict, Any, List, Optional, Tuple
import re
import logging
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk classification for database operations"""
    LOW = "low"              # Safe read-only operations, index creation
    MEDIUM = "medium"        # Data modifications with WHERE clause, schema changes
    HIGH = "high"            # Bulk modifications, missing WHERE clauses
    CRITICAL = "critical"    # System table modifications, DROP operations


class ImpactLevel(Enum):
    """Estimated impact of operation"""
    MINIMAL = "minimal"      # < 100 rows
    MODERATE = "moderate"    # 100-10K rows
    SIGNIFICANT = "significant"  # 10K-1M rows
    MASSIVE = "massive"      # > 1M rows


class SafetyValidator:
    """
    Validates MCP suggestions for safety, security, and operational risks.
    """

    def __init__(self, ds_id: str):
        """
        Initialize safety validator.

        Args:
            ds_id: Datasource ID for context
        """
        self.ds_id = ds_id

    async def validate_suggestion(
        self,
        suggestion: Dict[str, Any],
        agent: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive safety validation of MCP suggestion.

        Args:
            suggestion: MCP-generated suggestion
            agent: Optional database agent for impact estimation

        Returns:
            {
                "is_valid": bool,
                "is_safe": bool,
                "risk_level": str,
                "impact_level": str,
                "warnings": List[str],
                "blocking_issues": List[str],
                "recommendation": str,
                "suggestion": Dict (enhanced with safety metadata)
            }
        """
        sql = suggestion.get("sql", "")
        warnings = []
        blocking_issues = []

        logger.info(f"Validating suggestion: {suggestion.get('id')}")

        # 1. Basic SQL validation
        if not sql or not sql.strip():
            blocking_issues.append("No SQL provided")
            return self._build_invalid_response(blocking_issues, suggestion)

        # 2. Assess risk level
        risk_level = self._assess_risk(sql)

        # 3. Check for dangerous patterns
        dangerous, danger_warnings = self._check_dangerous_patterns(sql)
        if dangerous:
            warnings.extend(danger_warnings)
            risk_level = RiskLevel.CRITICAL

        # 4. Check for missing WHERE clauses
        missing_where, where_warnings = self._check_missing_where(sql)
        if missing_where:
            warnings.extend(where_warnings)
            if risk_level != RiskLevel.CRITICAL:
                risk_level = RiskLevel.HIGH

        # 5. Estimate impact (if agent available)
        impact_level = ImpactLevel.MODERATE
        impact_details = {}
        if agent:
            impact_level, impact_details = await self._estimate_impact(sql, agent)

        # 6. Check for SELECT * anti-pattern
        if self._has_select_star(sql):
            warnings.append("Uses SELECT * which may be inefficient")

        # 7. Validate table references
        tables_affected = self._extract_tables(sql)

        # 8. Check reversibility
        is_reversible = self._is_reversible(sql)

        # 9. Generate recommendation
        recommendation = self._generate_recommendation(
            risk_level,
            impact_level,
            is_reversible,
            warnings
        )

        # 10. Enhanced suggestion with safety metadata
        enhanced_suggestion = {
            **suggestion,
            "risk_level": risk_level.value,
            "impact_level": impact_level.value,
            "warnings": warnings,
            "blocking_issues": blocking_issues,
            "tables_affected": tables_affected,
            "is_reversible": is_reversible,
            "requires_backup": risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL],
            "requires_confirmation": risk_level != RiskLevel.LOW,
            "requires_double_confirmation": risk_level == RiskLevel.CRITICAL,
            "recommendation": recommendation,
            "impact_details": impact_details,
            "validated_at": datetime.utcnow().isoformat(),
            "status": "validated"
        }

        is_safe = risk_level != RiskLevel.CRITICAL and len(blocking_issues) == 0

        logger.info(
            f"Validation complete: risk={risk_level.value}, "
            f"safe={is_safe}, warnings={len(warnings)}"
        )

        return {
            "is_valid": len(blocking_issues) == 0,
            "is_safe": is_safe,
            "risk_level": risk_level.value,
            "impact_level": impact_level.value,
            "warnings": warnings,
            "blocking_issues": blocking_issues,
            "recommendation": recommendation,
            "suggestion": enhanced_suggestion
        }

    def _assess_risk(self, sql: str) -> RiskLevel:
        """
        Assess risk level based on SQL operation type.

        Risk Matrix:
        - CRITICAL: DROP DATABASE/SCHEMA, system table modifications
        - HIGH: UPDATE/DELETE without WHERE, DROP TABLE/INDEX
        - MEDIUM: UPDATE/DELETE with WHERE, schema changes
        - LOW: SELECT queries, CREATE INDEX
        """
        sql_upper = sql.upper()

        # CRITICAL: Database/schema level operations
        if re.search(r'\b(DROP|TRUNCATE|ALTER)\s+(DATABASE|SCHEMA)', sql_upper):
            return RiskLevel.CRITICAL

        # CRITICAL: System table modifications
        if re.search(r'\b(pg_|sys\.|information_schema\.)', sql_upper, re.IGNORECASE):
            return RiskLevel.CRITICAL

        # HIGH: Bulk deletions/truncations
        if re.search(r'\b(TRUNCATE|DROP\s+TABLE)\b', sql_upper):
            return RiskLevel.HIGH

        # HIGH: Data modification without WHERE
        if self._is_bulk_modification(sql_upper):
            return RiskLevel.HIGH

        # HIGH: DROP statements
        if re.search(r'\bDROP\s+(TABLE|INDEX|VIEW)\b', sql_upper):
            return RiskLevel.HIGH

        # MEDIUM: Data modifications with WHERE
        if re.search(r'\b(UPDATE|DELETE|INSERT)\b', sql_upper):
            return RiskLevel.MEDIUM

        # MEDIUM: Schema changes
        if re.search(r'\b(ALTER\s+TABLE|CREATE\s+INDEX|DROP\s+INDEX)\b', sql_upper):
            return RiskLevel.MEDIUM

        # LOW: Read-only operations
        if re.search(r'^\s*SELECT\b', sql_upper):
            return RiskLevel.LOW

        # LOW: CREATE INDEX (non-destructive)
        if re.search(r'^\s*CREATE\s+INDEX\b', sql_upper):
            return RiskLevel.LOW

        # Default to MEDIUM for unknown operations
        return RiskLevel.MEDIUM

    def _check_dangerous_patterns(self, sql: str) -> Tuple[bool, List[str]]:
        """
        Check for dangerous SQL patterns (SQL injection, etc.).

        Returns:
            (is_dangerous, list_of_warnings)
        """
        warnings = []
        sql_lower = sql.lower()

        # SQL injection patterns
        dangerous_patterns = [
            (r';\s*drop', "Contains SQL injection pattern: DROP after semicolon"),
            (r'--\s*drop', "Contains SQL injection pattern: DROP in comment"),
            (r'union\s+all\s+select', "Contains UNION-based injection pattern"),
            (r'exec\s*\(', "Contains dynamic SQL execution (EXEC)"),
            (r'execute\s+immediate', "Contains dynamic SQL execution"),
            (r'xp_cmdshell', "Contains system command execution attempt"),
            (r'into\s+outfile', "Contains file write operation"),
            (r'load_file', "Contains file read operation"),
        ]

        for pattern, warning in dangerous_patterns:
            if re.search(pattern, sql_lower):
                warnings.append(warning)

        return len(warnings) > 0, warnings

    def _check_missing_where(self, sql: str) -> Tuple[bool, List[str]]:
        """
        Check if UPDATE/DELETE is missing WHERE clause.

        Returns:
            (is_missing, list_of_warnings)
        """
        warnings = []
        sql_upper = sql.upper()

        # Check for UPDATE without WHERE
        if re.search(r'\bUPDATE\b', sql_upper):
            if not re.search(r'\bWHERE\b', sql_upper):
                warnings.append(
                    "⚠️ CRITICAL: UPDATE statement without WHERE clause will modify ALL rows"
                )
                return True, warnings

        # Check for DELETE without WHERE
        if re.search(r'\bDELETE\b', sql_upper):
            if not re.search(r'\bWHERE\b', sql_upper):
                warnings.append(
                    "⚠️ CRITICAL: DELETE statement without WHERE clause will delete ALL rows"
                )
                return True, warnings

        return False, warnings

    def _is_bulk_modification(self, sql_upper: str) -> bool:
        """Check if operation modifies data in bulk without WHERE."""
        if re.search(r'\b(UPDATE|DELETE)\b', sql_upper):
            return not re.search(r'\bWHERE\b', sql_upper)
        return False

    def _has_select_star(self, sql: str) -> bool:
        """Check for SELECT * anti-pattern."""
        return bool(re.search(r'\bSELECT\s+\*', sql, re.IGNORECASE))

    def _extract_tables(self, sql: str) -> List[str]:
        """
        Extract table names from SQL.

        Returns:
            List of table names
        """
        tables = set()

        # Patterns to extract table names
        patterns = [
            r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bUPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bINTO\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bTABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.update(matches)

        return list(tables)

    async def _estimate_impact(
        self,
        sql: str,
        agent: Any
    ) -> Tuple[ImpactLevel, Dict[str, Any]]:
        """
        Estimate the impact of executing this SQL.

        Uses database agent to query table statistics.

        Returns:
            (impact_level, impact_details)
        """
        try:
            # Extract tables
            tables = self._extract_tables(sql)

            if not tables:
                return ImpactLevel.MINIMAL, {"note": "No tables identified"}

            # Get table row counts (if agent supports it)
            total_rows = 0
            table_stats = {}

            # This is a placeholder - actual implementation would query database
            # for row counts per table
            # Example: SELECT COUNT(*) FROM table_name

            impact_details = {
                "tables": tables,
                "estimated_rows_affected": "Unknown (requires database query)",
                "table_stats": table_stats
            }

            # Rough estimation based on operation type
            sql_upper = sql.upper()
            if 'DELETE' in sql_upper or 'UPDATE' in sql_upper:
                if 'WHERE' not in sql_upper:
                    return ImpactLevel.MASSIVE, impact_details
                else:
                    return ImpactLevel.MODERATE, impact_details

            return ImpactLevel.MINIMAL, impact_details

        except Exception as e:
            logger.error(f"Impact estimation failed: {e}")
            return ImpactLevel.MODERATE, {"error": str(e)}

    def _is_reversible(self, sql: str) -> bool:
        """
        Check if operation is reversible.

        Non-reversible operations:
        - DROP (cannot recover dropped data)
        - TRUNCATE (faster than DELETE but no rollback)
        - DELETE (without backup)
        - UPDATE (without before-values)

        Reversible operations:
        - CREATE INDEX (can be dropped)
        - INSERT (can be deleted if you track IDs)
        - SELECT (read-only)
        """
        sql_upper = sql.upper()

        # Non-reversible operations
        non_reversible = ['DROP', 'TRUNCATE']
        for op in non_reversible:
            if re.search(rf'\b{op}\b', sql_upper):
                return False

        # Partially reversible (requires backup or before-values)
        if re.search(r'\b(DELETE|UPDATE)\b', sql_upper):
            return False

        # Reversible operations
        if re.search(r'\b(CREATE\s+INDEX|SELECT)\b', sql_upper):
            return True

        # INSERT is partially reversible if you track inserted IDs
        if re.search(r'\bINSERT\b', sql_upper):
            return False

        # Default to non-reversible for safety
        return False

    def _generate_recommendation(
        self,
        risk_level: RiskLevel,
        impact_level: ImpactLevel,
        is_reversible: bool,
        warnings: List[str]
    ) -> str:
        """Generate human-readable recommendation for user."""
        if risk_level == RiskLevel.CRITICAL:
            return (
                "🚨 CRITICAL RISK: This operation could cause irreversible damage. "
                "Create a full database backup before proceeding. "
                "Consider testing in a development environment first."
            )

        if risk_level == RiskLevel.HIGH:
            if not is_reversible:
                return (
                    "⚠️ HIGH RISK: This operation is NOT reversible. "
                    "Create a backup of affected tables before executing. "
                    "Verify the SQL carefully."
                )
            else:
                return (
                    "⚠️ HIGH RISK: This operation affects many rows. "
                    "Review the SQL carefully and have a rollback plan ready."
                )

        if risk_level == RiskLevel.MEDIUM:
            return (
                "⚡ MEDIUM RISK: This operation modifies data. "
                "Review the changes and ensure you have recent backups."
            )

        # LOW risk
        if len(warnings) > 0:
            return (
                "✅ LOW RISK: This operation is relatively safe, "
                "but review the warnings above."
            )

        return "✅ LOW RISK: This operation is safe to execute."

    def _build_invalid_response(
        self,
        blocking_issues: List[str],
        suggestion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build response for invalid suggestions."""
        return {
            "is_valid": False,
            "is_safe": False,
            "risk_level": RiskLevel.CRITICAL.value,
            "impact_level": ImpactLevel.MINIMAL.value,
            "warnings": [],
            "blocking_issues": blocking_issues,
            "recommendation": "Cannot validate: " + "; ".join(blocking_issues),
            "suggestion": {
                **suggestion,
                "status": "invalid",
                "validated_at": datetime.utcnow().isoformat()
            }
        }
