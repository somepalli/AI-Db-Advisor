"""
Database Agent Registry
Maps database engine names to their respective agent implementations
"""
from .base_agent import BaseAgent
from .postgres_agent import PostgresAgent
from .mysql_agent import MySQLAgent
from .sqlserver_agent import SQLServerAgent
from .mongodb_agent import MongoDBAgent
from .oracle_agent import OracleAgent
from .redis_agent import RedisAgent
from .sqlite_agent import SQLiteAgent
from .cassandra_agent import CassandraAgent

# Supported database engines
SUPPORTED_ENGINES = {
    # PostgreSQL
    "postgres": PostgresAgent,
    "postgresql": PostgresAgent,
    "pg": PostgresAgent,

    # MySQL / MariaDB
    "mysql": MySQLAgent,
    "mariadb": MySQLAgent,

    # SQL Server
    "sqlserver": SQLServerAgent,
    "mssql": SQLServerAgent,
    "sql-server": SQLServerAgent,

    # MongoDB
    "mongodb": MongoDBAgent,
    "mongo": MongoDBAgent,

    # Oracle Database
    "oracle": OracleAgent,
    "oracle-db": OracleAgent,

    # Redis
    "redis": RedisAgent,

    # SQLite
    "sqlite": SQLiteAgent,
    "sqlite3": SQLiteAgent,

    # Cassandra
    "cassandra": CassandraAgent,
    "cassandra-db": CassandraAgent,
}

def get_agent_for(engine: str, dsn: str) -> BaseAgent:
    """
    Get database agent for given engine type.

    Args:
        engine: Database engine name (postgres, mysql, sqlserver, mongodb, etc.)
        dsn: Database connection string

    Returns:
        BaseAgent: Configured database agent

    Raises:
        ValueError: If engine is not supported
    """
    engine_lower = engine.lower()

    if engine_lower in SUPPORTED_ENGINES:
        agent_class = SUPPORTED_ENGINES[engine_lower]
        return agent_class(dsn)

    # List supported engines in error message
    supported_list = ", ".join(sorted(set(SUPPORTED_ENGINES.keys())))
    raise ValueError(
        f"Unsupported engine: '{engine}'. "
        f"Supported engines: {supported_list}"
    )

def get_supported_engines() -> list:
    """Get list of all supported database engines"""
    return sorted(set(SUPPORTED_ENGINES.keys()))
