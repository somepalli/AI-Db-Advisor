"""
Advanced metrics collector for comprehensive database monitoring.

Collects all metrics required for the 16 alert rules:
- Basic connectivity and size metrics
- Performance metrics (latency, throughput)
- Resource utilization (CPU, memory, disk)
- Replication and backup status
- Database health indicators (bloat, checkpoints, cache)
"""

import logging
import os
import psutil
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _default_disk_path() -> str:
    """Filesystem root for disk-usage checks, cross-platform.

    Returns ``C:\\`` on Windows and ``/`` on Linux/macOS, rather than assuming a
    Windows drive letter.
    """
    return os.path.abspath(os.sep)


class MetricsCollector:
    """
    Comprehensive metrics collector for PostgreSQL databases.

    Collects all metrics needed for the 16 alert rules across P1/P2/P3 severities.
    """

    def __init__(self, agent):
        """
        Initialize metrics collector with database agent.

        Args:
            agent: Database agent instance (e.g., PostgresAgent)
        """
        self.agent = agent
        self.db_type = agent.get_db_type()

        # Metric history for latency calculations
        self._last_query_stats = None
        self._last_checkpoint_stats = None
        self._last_deadlock_stats = None

    def collect_all_metrics(self, datasource_id: str) -> Dict[str, Any]:
        """
        Collect all metrics for alert evaluation.

        Returns dict with all metrics required by the 16 alert rules.
        """
        logger.info(f"[MetricsCollector] Collecting comprehensive metrics for {datasource_id}")

        metrics = {}

        try:
            # Basic connectivity and database stats
            basic_metrics = self._collect_basic_metrics()
            metrics.update(basic_metrics)

            # Performance metrics (latency, query performance)
            perf_metrics = self._collect_performance_metrics()
            metrics.update(perf_metrics)

            # Resource utilization (CPU, memory, disk)
            resource_metrics = self._collect_resource_metrics()
            metrics.update(resource_metrics)

            # Replication and backup status
            replication_metrics = self._collect_replication_metrics()
            metrics.update(replication_metrics)

            # Database health (bloat, checkpoints, cache, indexes)
            health_metrics = self._collect_health_metrics()
            metrics.update(health_metrics)

            logger.info(f"[MetricsCollector] Collected {len(metrics)} metrics for {datasource_id}")
            return metrics

        except Exception as e:
            logger.error(f"[MetricsCollector] Failed to collect metrics: {e}", exc_info=True)
            return self._empty_metrics()

    def _collect_basic_metrics(self) -> Dict[str, Any]:
        """Collect basic connectivity and database size metrics."""
        metrics = {}

        try:
            # Test database connectivity
            db_up = True
            try:
                schema = self.agent.get_schema()
                table_count = len(schema.get("tables", {}))
            except Exception as e:
                logger.error(f"[MetricsCollector] Database connectivity failed: {e}")
                db_up = False
                table_count = 0

            metrics["db_up"] = 1 if db_up else 0
            metrics["table_count"] = table_count

            # Get basic database stats
            stats = self.agent.stats()
            metrics["connection_count"] = stats.get("active_backends", 0)

            # Parse database size
            db_size_str = stats.get("total_db_size", "0")
            metrics["db_size_mb"] = self._parse_size_to_mb(db_size_str)

            # Get lock counts
            locks = self.agent.locks()
            metrics["lock_count"] = len(locks)
            metrics["blocking_locks"] = len([l for l in locks if not l.get("granted", True)])

        except Exception as e:
            logger.error(f"[MetricsCollector] Error collecting basic metrics: {e}")
            metrics.update({
                "db_up": 0,
                "table_count": 0,
                "connection_count": 0,
                "db_size_mb": 0,
                "lock_count": 0,
                "blocking_locks": 0
            })

        return metrics

    def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect query performance metrics (latency, throughput)."""
        metrics = {
            "write_p99_latency_ms": 0.0,
            "read_p99_latency_ms": 0.0,
            "deadlocks_per_minute": 0.0
        }

        try:
            # Query pg_stat_statements for latency percentiles
            query_stats_sql = """
            SELECT
                -- Write queries (INSERT, UPDATE, DELETE)
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY mean_exec_time)
                    FILTER (WHERE query ~* '^(INSERT|UPDATE|DELETE)') AS write_p99_ms,

                -- Read queries (SELECT)
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY mean_exec_time)
                    FILTER (WHERE query ~* '^SELECT') AS read_p99_ms,

                -- Total queries for throughput
                SUM(calls) AS total_calls
            FROM pg_stat_statements;
            """

            with self.agent._conn() as c, c.cursor() as cur:
                try:
                    cur.execute(query_stats_sql)
                    result = cur.fetchone()

                    if result:
                        metrics["write_p99_latency_ms"] = float(result.get("write_p99_ms") or 0)
                        metrics["read_p99_latency_ms"] = float(result.get("read_p99_ms") or 0)

                except Exception as e:
                    logger.warning(f"[MetricsCollector] pg_stat_statements query failed: {e}")

            # Query deadlock statistics
            deadlock_sql = """
            SELECT deadlocks
            FROM pg_stat_database
            WHERE datname = current_database();
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(deadlock_sql)
                result = cur.fetchone()

                if result:
                    current_deadlocks = result.get("deadlocks", 0)

                    # Calculate deadlocks per minute
                    if self._last_deadlock_stats:
                        deadlock_delta = current_deadlocks - self._last_deadlock_stats["count"]
                        time_delta_minutes = (time.time() - self._last_deadlock_stats["timestamp"]) / 60.0

                        if time_delta_minutes > 0:
                            metrics["deadlocks_per_minute"] = deadlock_delta / time_delta_minutes

                    # Store for next iteration
                    self._last_deadlock_stats = {
                        "count": current_deadlocks,
                        "timestamp": time.time()
                    }

        except Exception as e:
            logger.error(f"[MetricsCollector] Error collecting performance metrics: {e}")

        return metrics

    def _collect_resource_metrics(self) -> Dict[str, Any]:
        """Collect CPU, memory, and disk utilization metrics."""
        metrics = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "disk_free_percent": 0.0
        }

        try:
            # Get CPU and memory usage
            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)

            memory = psutil.virtual_memory()
            metrics["memory_percent"] = memory.percent

            # Get disk usage for PostgreSQL data directory
            # Try to get data directory from PostgreSQL
            try:
                with self.agent._conn() as c, c.cursor() as cur:
                    cur.execute("SHOW data_directory;")
                    result = cur.fetchone()
                    data_dir = result.get("data_directory") or _default_disk_path()

                    disk = psutil.disk_usage(data_dir)
                    metrics["disk_free_percent"] = (disk.free / disk.total) * 100
            except Exception:
                # Fallback to the filesystem root (cross-platform)
                disk = psutil.disk_usage(_default_disk_path())
                metrics["disk_free_percent"] = (disk.free / disk.total) * 100

            # Get connection pool utilization
            connection_limit_sql = """
            SELECT
                (SELECT count(*) FROM pg_stat_activity) AS current_connections,
                (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections;
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(connection_limit_sql)
                result = cur.fetchone()

                if result:
                    current = result.get("current_connections", 0)
                    max_conn = result.get("max_connections", 100)

                    if max_conn > 0:
                        metrics["connection_utilization_percent"] = (current / max_conn) * 100
                    else:
                        metrics["connection_utilization_percent"] = 0.0

        except Exception as e:
            logger.error(f"[MetricsCollector] Error collecting resource metrics: {e}")

        return metrics

    def _collect_replication_metrics(self) -> Dict[str, Any]:
        """Collect replication lag and backup status metrics."""
        metrics = {
            "replay_lag_seconds": 0.0,
            "last_backup_hours_ago": 9999.0  # Default to very high value
        }

        try:
            # Check replication lag (for replicas)
            replication_sql = """
            SELECT
                CASE
                    WHEN pg_is_in_recovery() THEN
                        EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))
                    ELSE
                        0
                END AS replay_lag_seconds;
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(replication_sql)
                result = cur.fetchone()

                if result:
                    metrics["replay_lag_seconds"] = float(result.get("replay_lag_seconds") or 0)

            # Check last backup time (from pg_stat_archiver or custom table)
            # Note: This requires archiving to be configured
            backup_sql = """
            SELECT
                EXTRACT(EPOCH FROM (now() - last_archived_time)) / 3600 AS hours_since_last_archive
            FROM pg_stat_archiver;
            """

            try:
                with self.agent._conn() as c, c.cursor() as cur:
                    cur.execute(backup_sql)
                    result = cur.fetchone()

                    if result and result.get("hours_since_last_archive") is not None:
                        metrics["last_backup_hours_ago"] = float(result.get("hours_since_last_archive"))
            except Exception:
                # Archive status not available - set to 0 to avoid false alerts
                metrics["last_backup_hours_ago"] = 0.0

        except Exception as e:
            logger.error(f"[MetricsCollector] Error collecting replication metrics: {e}")

        return metrics

    def _collect_health_metrics(self) -> Dict[str, Any]:
        """Collect database health metrics (bloat, checkpoints, cache, indexes)."""
        metrics = {
            "max_transaction_age_minutes": 0.0,
            "max_table_bloat_percent": 0.0,
            "checkpoint_write_time_seconds": 0.0,
            "storage_runway_days": 9999.0,
            "cache_hit_ratio_percent": 100.0,
            "unused_index_count": 0
        }

        try:
            # Long running transactions
            transaction_age_sql = """
            SELECT
                EXTRACT(EPOCH FROM (now() - xact_start)) / 60 AS transaction_age_minutes
            FROM pg_stat_activity
            WHERE xact_start IS NOT NULL
              AND state <> 'idle'
            ORDER BY xact_start ASC
            LIMIT 1;
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(transaction_age_sql)
                result = cur.fetchone()

                if result and result.get("transaction_age_minutes") is not None:
                    metrics["max_transaction_age_minutes"] = float(result.get("transaction_age_minutes"))

            # Table bloat (simplified estimation)
            bloat_sql = """
            SELECT
                schemaname,
                tablename,
                pg_total_relation_size(schemaname || '.' || tablename) AS total_bytes,
                pg_relation_size(schemaname || '.' || tablename) AS table_bytes,
                CASE
                    WHEN pg_total_relation_size(schemaname || '.' || tablename) > 0 THEN
                        ((pg_total_relation_size(schemaname || '.' || tablename) - pg_relation_size(schemaname || '.' || tablename))::float /
                         pg_total_relation_size(schemaname || '.' || tablename)::float * 100)
                    ELSE 0
                END AS bloat_percent
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY bloat_percent DESC
            LIMIT 1;
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(bloat_sql)
                result = cur.fetchone()

                if result and result.get("bloat_percent") is not None:
                    metrics["max_table_bloat_percent"] = float(result.get("bloat_percent"))

            # Checkpoint statistics
            checkpoint_sql = """
            SELECT
                checkpoints_timed,
                checkpoints_req,
                checkpoint_write_time,
                checkpoint_sync_time
            FROM pg_stat_bgwriter;
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(checkpoint_sql)
                result = cur.fetchone()

                if result:
                    write_time_ms = result.get("checkpoint_write_time", 0)

                    # Calculate write time per checkpoint
                    if self._last_checkpoint_stats:
                        write_delta = write_time_ms - self._last_checkpoint_stats["write_time"]
                        checkpoint_delta = (result.get("checkpoints_timed", 0) + result.get("checkpoints_req", 0)) - \
                                         self._last_checkpoint_stats["total_checkpoints"]

                        if checkpoint_delta > 0:
                            # Average write time per checkpoint in seconds
                            metrics["checkpoint_write_time_seconds"] = (write_delta / checkpoint_delta) / 1000.0

                    # Store for next iteration
                    self._last_checkpoint_stats = {
                        "write_time": write_time_ms,
                        "total_checkpoints": result.get("checkpoints_timed", 0) + result.get("checkpoints_req", 0)
                    }

            # Storage forecast (growth rate estimation)
            storage_sql = """
            SELECT pg_database_size(current_database()) AS current_size_bytes;
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(storage_sql)
                result = cur.fetchone()

                if result:
                    current_size_mb = result.get("current_size_bytes", 0) / (1024.0 * 1024.0)

                    # Simple estimation: assume 1GB/day growth, 100GB disk available
                    # In production, this should use historical growth data
                    estimated_daily_growth_mb = 1024.0  # 1GB/day
                    available_disk_mb = (psutil.disk_usage(_default_disk_path()).free / (1024.0 * 1024.0))

                    if estimated_daily_growth_mb > 0:
                        metrics["storage_runway_days"] = available_disk_mb / estimated_daily_growth_mb
                    else:
                        metrics["storage_runway_days"] = 9999.0

            # Cache hit ratio
            cache_sql = """
            SELECT
                sum(heap_blks_read) AS heap_read,
                sum(heap_blks_hit) AS heap_hit,
                CASE
                    WHEN (sum(heap_blks_read) + sum(heap_blks_hit)) > 0 THEN
                        (sum(heap_blks_hit)::float / (sum(heap_blks_read) + sum(heap_blks_hit))::float * 100)
                    ELSE 100
                END AS cache_hit_ratio
            FROM pg_statio_user_tables;
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(cache_sql)
                result = cur.fetchone()

                if result and result.get("cache_hit_ratio") is not None:
                    metrics["cache_hit_ratio_percent"] = float(result.get("cache_hit_ratio"))

            # Unused indexes
            unused_index_sql = """
            SELECT COUNT(*) AS unused_count
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
              AND indexrelname NOT LIKE '%_pkey';
            """

            with self.agent._conn() as c, c.cursor() as cur:
                cur.execute(unused_index_sql)
                result = cur.fetchone()

                if result:
                    metrics["unused_index_count"] = int(result.get("unused_count", 0))

        except Exception as e:
            logger.error(f"[MetricsCollector] Error collecting health metrics: {e}")

        return metrics

    def _parse_size_to_mb(self, size_value: Any) -> float:
        """Parse database size to MB (handles both string and integer formats)."""
        try:
            # If it's already a number (bytes), convert to MB
            if isinstance(size_value, (int, float)):
                return float(size_value) / (1024.0 * 1024.0)

            # If it's a string like "150 MB", parse it
            if isinstance(size_value, str):
                parts = size_value.strip().split()
                if len(parts) >= 2:
                    value = float(parts[0])
                    unit = parts[1].upper()

                    # Convert to MB
                    if unit == 'BYTES' or unit == 'B':
                        return value / (1024.0 * 1024.0)
                    elif unit == 'KB':
                        return value / 1024.0
                    elif unit == 'MB':
                        return value
                    elif unit == 'GB':
                        return value * 1024.0
                    elif unit == 'TB':
                        return value * 1024.0 * 1024.0
                elif len(parts) == 1:
                    # Just a number, assume bytes
                    return float(parts[0]) / (1024.0 * 1024.0)

            return 0.0

        except Exception as e:
            logger.warning(f"[MetricsCollector] Failed to parse size '{size_value}': {e}")
            return 0.0

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics dict for error cases."""
        return {
            # Basic metrics
            "db_up": 0,
            "connection_count": 0,
            "db_size_mb": 0,
            "table_count": 0,
            "lock_count": 0,
            "blocking_locks": 0,

            # Performance metrics
            "write_p99_latency_ms": 0.0,
            "read_p99_latency_ms": 0.0,
            "deadlocks_per_minute": 0.0,

            # Resource metrics
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "disk_free_percent": 0.0,
            "connection_utilization_percent": 0.0,

            # Replication and backup
            "replay_lag_seconds": 0.0,
            "last_backup_hours_ago": 0.0,

            # Health metrics
            "max_transaction_age_minutes": 0.0,
            "max_table_bloat_percent": 0.0,
            "checkpoint_write_time_seconds": 0.0,
            "storage_runway_days": 9999.0,
            "cache_hit_ratio_percent": 100.0,
            "unused_index_count": 0
        }


def collect_all_metrics(datasource_id: str) -> Dict[str, Any]:
    """Resolve the datasource's agent and collect all metrics for alert evaluation.

    This is the single shared entry point used by BOTH the manual ``/alerts/evaluate``
    endpoint and the background monitoring service, so alert behaviour is consistent.
    """
    from ..deps import resolve_agent  # local import to avoid circular dependency

    agent = resolve_agent(datasource_id)
    collector = MetricsCollector(agent)
    metrics = collector.collect_all_metrics(datasource_id)
    metrics.setdefault("datasource_id", datasource_id)
    metrics.setdefault("timestamp", datetime.now().isoformat())
    return metrics
