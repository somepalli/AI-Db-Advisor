"""
Cassandra Agent
Supports Apache Cassandra with AI-powered optimization
"""
from .base_agent import BaseAgent
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class CassandraAgent(BaseAgent):
    """
    Apache Cassandra database agent (NoSQL wide-column store).
    Connection string format: cassandra://host:port/keyspace
    or: cassandra://user:password@host:port/keyspace
    """

    def get_db_type(self) -> str:
        return "cassandra"

    def _conn(self):
        """Create Cassandra connection using cassandra-driver"""
        try:
            from cassandra.cluster import Cluster
            from cassandra.auth import PlainTextAuthProvider
            from urllib.parse import urlparse

            parsed = urlparse(self.dsn)

            # Extract keyspace from path
            keyspace = parsed.path.lstrip('/') if parsed.path else 'system'

            # Setup auth if credentials provided
            auth_provider = None
            if parsed.username and parsed.password:
                auth_provider = PlainTextAuthProvider(
                    username=parsed.username,
                    password=parsed.password
                )

            # Create cluster connection
            cluster = Cluster(
                contact_points=[parsed.hostname or 'localhost'],
                port=parsed.port or 9042,
                auth_provider=auth_provider
            )

            session = cluster.connect(keyspace)
            return session
        except ImportError:
            raise Exception("cassandra-driver not installed. Run: pip install cassandra-driver")

    def get_schema(self) -> Dict[str, Any]:
        """Get Cassandra schema (keyspace tables and columns)"""
        session = self._conn()

        try:
            # Get current keyspace
            keyspace = session.keyspace

            # Query system schema for tables in current keyspace
            query = """
            SELECT table_name FROM system_schema.tables
            WHERE keyspace_name = %s
            """
            tables_result = session.execute(query, [keyspace])

            schema: Dict[str, Any] = {}

            for row in tables_result:
                table_name = row.table_name

                # Get columns for this table
                columns_query = """
                SELECT column_name, type, kind
                FROM system_schema.columns
                WHERE keyspace_name = %s AND table_name = %s
                """
                columns_result = session.execute(columns_query, [keyspace, table_name])

                columns = []
                for col in columns_result:
                    columns.append({
                        "column": col.column_name,
                        "type": col.type,
                        "nullable": "YES",  # Cassandra columns are nullable by default
                        "kind": col.kind  # partition_key, clustering, regular
                    })

                schema[f"{keyspace}.{table_name}"] = columns

            return {"tables": schema}
        finally:
            session.cluster.shutdown()

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Cassandra doesn't track query stats in standard way - return empty list"""
        logger.info("Cassandra doesn't provide built-in query statistics")
        return []

    def explain(self, query_filter: str, analyze: bool = False) -> Dict[str, Any]:
        """Get Cassandra query trace"""
        session = self._conn()

        try:
            # Enable tracing
            session.default_trace = True

            # Execute query to get trace
            future = session.execute_async(query_filter)
            result = future.result()

            # Get trace
            trace = future.get_query_trace()

            if trace:
                trace_events = []
                for event in trace.events:
                    trace_events.append({
                        "activity": event.description,
                        "source": str(event.source),
                        "elapsed_micros": event.source_elapsed
                    })

                return {
                    "plan": {
                        "duration_micros": trace.duration,
                        "coordinator": str(trace.coordinator),
                        "events": trace_events
                    },
                    "format": "cassandra_trace"
                }
            else:
                return {"plan": None, "error": "Trace not available"}

        except Exception as e:
            logger.error(f"TRACE failed: {e}")
            return {"plan": None, "error": str(e)}
        finally:
            session.cluster.shutdown()

    def locks(self) -> List[Dict[str, Any]]:
        """Cassandra uses eventual consistency - no traditional locks"""
        logger.info("Cassandra uses eventual consistency (no traditional locks)")
        return []

    def stats(self) -> Dict[str, Any]:
        """Get Cassandra cluster statistics"""
        session = self._conn()

        try:
            # Get keyspace size estimate
            keyspace = session.keyspace

            query = """
            SELECT SUM(mean_partition_size * partitions_count) as estimated_size
            FROM system.size_estimates
            WHERE keyspace_name = %s
            """
            result = session.execute(query, [keyspace])
            row = result.one()

            estimated_size = int(row.estimated_size if row and row.estimated_size else 0)

            # Get cluster size (number of nodes)
            cluster_size = len(session.cluster.metadata.all_hosts())

            return {
                "total_db_size": estimated_size,
                "active_backends": cluster_size
            }
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return {"total_db_size": 0, "active_backends": 0}
        finally:
            session.cluster.shutdown()

    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing Cassandra indexes"""
        session = self._conn()

        try:
            keyspace = session.keyspace

            # Query for indexes
            query = """
            SELECT index_name, options
            FROM system_schema.indexes
            WHERE keyspace_name = %s
            """

            params = [keyspace]
            if table_name:
                query += " AND table_name = %s"
                params.append(table_name)

            result = session.execute(query, params)

            indexes = []
            for row in result:
                # Extract target column from options
                target = row.options.get('target', '') if row.options else ''

                indexes.append({
                    "table_schema": keyspace,
                    "table_name_short": table_name if table_name else "unknown",
                    "table_name": f"{keyspace}.{table_name}" if table_name else f"{keyspace}.unknown",
                    "index_name": row.index_name,
                    "columns": [target] if target else [],
                    "is_unique": False,  # Cassandra secondary indexes are not unique
                    "index_type": "secondary"
                })

            return indexes
        finally:
            session.cluster.shutdown()

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Check if Cassandra index exists"""
        existing = self.get_existing_indexes(table_name)
        columns_normalized = [c.lower().strip() for c in columns]

        for idx in existing:
            idx_columns = [c.lower().strip() for c in idx['columns']]
            if columns_normalized == idx_columns[:len(columns_normalized)]:
                logger.info(f"Index already exists: {idx['index_name']} on {idx['table_name_short']}")
                return True

        return False

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get Cassandra-specific optimization context"""
        session = self._conn()

        try:
            keyspace = session.keyspace

            # Get Cassandra version
            result = session.execute("SELECT release_version FROM system.local")
            version = result.one().release_version if result else "unknown"

            # Get table count
            query = """
            SELECT COUNT(*) as count
            FROM system_schema.tables
            WHERE keyspace_name = %s
            """
            result = session.execute(query, [keyspace])
            table_count = result.one().count

            # Get index count
            query = """
            SELECT COUNT(*) as count
            FROM system_schema.indexes
            WHERE keyspace_name = %s
            """
            result = session.execute(query, [keyspace])
            index_count = result.one().count

            stats = self.stats()

            return {
                "db_type": "cassandra",
                "version": version,
                "total_size": stats.get("total_db_size", 0),
                "table_count": table_count,
                "index_count": index_count
            }
        finally:
            session.cluster.shutdown()
