from typing import List, Dict, Any, Optional

class BaseAgent:
    """
    Base agent interface for database-agnostic operations.
    Each database type (PostgreSQL, MySQL, Oracle, etc.) implements this interface.
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.db_type = self.get_db_type()

    def get_db_type(self) -> str:
        """Return the database type (postgres, mysql, oracle, etc.)"""
        raise NotImplementedError

    # Core discovery methods (required for all databases)
    def get_schema(self) -> Dict[str, Any]:
        """Get database schema (tables, columns, types)"""
        raise NotImplementedError

    def get_database_objects(self) -> Dict[str, Any]:
        """
        Get a pgAdmin-style inventory of database objects for the schema tree:
        tables (with columns), views, sequences, functions/procedures, triggers.

        Default implementation derives tables from get_schema(); engines that
        support richer catalogs (e.g. PostgreSQL) override this.
        """
        schema = self.get_schema()
        return {
            "database": self.get_db_type(),
            "tables": schema.get("tables", {}),
            "views": {},
            "sequences": [],
            "functions": [],
            "triggers": [],
        }

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get top queries by execution time"""
        raise NotImplementedError

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        """Get query execution plan"""
        raise NotImplementedError

    def locks(self) -> List[Dict[str, Any]]:
        """Get current database locks"""
        raise NotImplementedError

    def stats(self) -> Dict[str, Any]:
        """Get database statistics (size, connections, etc.)"""
        raise NotImplementedError

    # Index management (SQL databases)
    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing indexes, optionally filtered by table"""
        # Default: return empty for NoSQL databases
        return []

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Check if an index exists on given columns"""
        # Default: return False for NoSQL databases
        return False

    def hypothetical_index(self, table: str, columns: List[str], include=None, method=None) -> Dict[str, Any]:
        """Create hypothetical index for testing (if supported)"""
        return {"hypo_stmt": None, "supported": False}

    def plan_with_hypo(self, sql: str, idx_stmt: str) -> Dict[str, Any]:
        """Get execution plan with hypothetical index"""
        return {"plan": None, "validated": False}

    # Database-specific optimization queries
    def get_optimization_context(self) -> Dict[str, Any]:
        """
        Get database-specific context for AI optimization.
        Override in each agent to provide relevant metrics.
        """
        return {
            "db_type": self.db_type,
            "version": "unknown",
            "total_size": 0,
            "table_count": 0,
            "index_count": 0
        }
