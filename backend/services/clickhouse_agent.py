import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class _ClickHouseConnWrapper:
    """Lightweight wrapper to provide a cursor-like interface for context builder."""

    client: "clickhouse_connect.driver.client.Client"

    def cursor(self) -> "_ClickHouseCursor":
        return _ClickHouseCursor(self.client)

    # Support usage in context managers where applicable
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        # clickhouse-connect is stateless; nothing to close.
        return None


class _ClickHouseCursor:
    """Minimal cursor that mimics DB-API behaviour for ClickHouse results."""

    def __init__(self, client: "clickhouse_connect.driver.client.Client"):
        self._client = client
        self._result: Optional["clickhouse_connect.driver.query.QueryResult"] = None
        self.description: Optional[List[Any]] = None

    def execute(self, sql: str):
        self._result = self._client.query(sql)
        self.description = [(name, None, None, None, None, None, None) for name in self._result.column_names]

    def fetchall(self):
        if not self._result:
            return []
        return self._result.result_rows

    def close(self):
        self._result = None
        self.description = None


class ClickHouseAgent(BaseAgent):
    """ClickHouse agent implementation using clickhouse-connect HTTP client."""

    def __init__(self, dsn: str):
        super().__init__(dsn)
        self._conn_params = self._parse_dsn(dsn)
        self._client = self._create_client()
        self._database = self._conn_params.get("database") or "default"

    def get_db_type(self) -> str:
        return "clickhouse"

    def _parse_dsn(self, dsn: str) -> Dict[str, Any]:
        url = urlparse(dsn)
        scheme = (url.scheme or "clickhouse").lower()

        secure = False
        if scheme in ("clickhouse+https", "https"):
            secure = True
        elif scheme in ("clickhouse", "clickhouse+http", "http"):
            secure = False
        else:
            raise ValueError(f"Unsupported ClickHouse DSN scheme: {scheme}")

        host = url.hostname or "localhost"
        port = url.port or (8443 if secure else 8123)
        username = url.username or "default"
        password = url.password or ""
        database = url.path.lstrip("/") or None

        params = parse_qs(url.query)
        if "database" in params and not database:
            database = params["database"][0]
        if "secure" in params:
            secure = params["secure"][0].lower() in ("1", "true", "yes")

        extra_options = {k: v[0] for k, v in params.items() if k not in {"database", "secure"}}

        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "database": database,
            "secure": secure,
            "settings": extra_options or None,
        }

    def _create_client(self):
        try:
            import clickhouse_connect  # type: ignore
        except ImportError as exc:
            raise ValueError(
                "clickhouse-connect is required for ClickHouse support. "
                "Install it with `pip install clickhouse-connect`."
            ) from exc

        params = self._conn_params.copy()
        settings = params.pop("settings", None)
        if settings:
            params["settings"] = settings

        try:
            client = clickhouse_connect.get_client(**params)
            client.ping()
            return client
        except Exception as exc:
            raise ValueError(f"Failed to connect to ClickHouse: {exc}") from exc

    def _conn(self) -> _ClickHouseConnWrapper:
        return _ClickHouseConnWrapper(self._client)

    def _query_dicts(self, sql: str) -> List[Dict[str, Any]]:
        result = self._client.query(sql)
        columns = result.column_names
        return [dict(zip(columns, row)) for row in result.result_rows]

    def get_schema(self) -> Dict[str, Any]:
        sql = f"""
        SELECT
            table AS table_name,
            name AS column_name,
            type AS data_type,
            position AS ordinal_position
        FROM system.columns
        WHERE database = '{self._database}'
        ORDER BY table_name, ordinal_position
        """

        rows = self._query_dicts(sql)
        tables: Dict[str, List[Dict[str, Any]]] = {}

        for row in rows:
            table = row["table_name"]
            column_type = row["data_type"]
            nullable = "YES" if column_type.startswith("Nullable(") else "NO"

            tables.setdefault(table, []).append(
                {
                    "column": row["column_name"],
                    "type": column_type,
                    "nullable": nullable,
                }
            )

        # Namespace tables with database for consistency with other agents
        return {
            "tables": {f"{self._database}.{table}": cols for table, cols in tables.items()}
        }

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        window_minutes = max(1, min(window_minutes, 1440))
        limit = max(1, min(limit, 100))

        query = f"""
        SELECT
            query,
            count() AS calls,
            round(avg(query_duration_ms), 2) AS mean_time_ms,
            sum(read_rows) AS read_rows
        FROM system.query_log
        WHERE type = 'QueryFinish'
          AND event_time >= now() - INTERVAL {window_minutes} MINUTE
          AND query NOT ILIKE '/* AI DB Advisor %'
          AND query != ''
        GROUP BY query
        ORDER BY mean_time_ms DESC
        LIMIT {limit}
        """

        try:
            rows = self._query_dicts(query)
            formatted = []
            for row in rows:
                formatted.append(
                    {
                        "query": row.get("query", "").strip(),
                        "calls": int(row.get("calls", 0)),
                        "mean_time_ms": float(row.get("mean_time_ms", 0)),
                        "rows": int(row.get("read_rows", 0)),
                        "source": "system.query_log",
                    }
                )
            if formatted:
                return formatted
        except Exception as exc:
            logger.warning("ClickHouse query_log unavailable: %s", exc)

        # Fallback to currently running queries
        try:
            running = self._query_dicts(
                """
                SELECT query, elapsed AS mean_time_ms, read_rows
                FROM system.processes
                WHERE is_initial_query = 1
                ORDER BY mean_time_ms DESC
                LIMIT {limit}
                """.format(limit=limit)
            )
            return [
                {
                    "query": row.get("query", "").strip(),
                    "calls": 1,
                    "mean_time_ms": float(row.get("mean_time_ms", 0)) * 1000,
                    "rows": int(row.get("read_rows", 0)),
                    "source": "system.processes",
                    "note": "query_log disabled; displaying currently running queries",
                }
                for row in running
            ]
        except Exception as exc:
            logger.error("Failed to read ClickHouse process list: %s", exc)
            return []

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        cleaned_sql = sql.strip().rstrip(";")
        explain_sql = f"EXPLAIN json=1 {cleaned_sql}"

        try:
            result = self._client.query(explain_sql)
            raw_plan = result.result_rows[0][0] if result.result_rows else "{}"
            plan = json.loads(raw_plan)
            return {"plan": plan}
        except Exception as exc:
            logger.warning("JSON explain failed for ClickHouse: %s", exc)
            try:
                result = self._client.query(f"EXPLAIN AST {cleaned_sql}")
                plan_lines = [row[0] for row in result.result_rows]
                return {"plan": plan_lines}
            except Exception as inner:
                raise ValueError(f"Failed to explain ClickHouse query: {inner}") from inner

    def locks(self) -> List[Dict[str, Any]]:
        # ClickHouse doesn't expose traditional locks; return empty list.
        return []

    def stats(self) -> Dict[str, Any]:
        try:
            db_stats = self._query_dicts(
                f"""
                SELECT
                    sum(bytes_on_disk) AS total_bytes
                FROM system.parts
                WHERE active AND database = '{self._database}'
                """
            )
            total_bytes = int(db_stats[0]["total_bytes"]) if db_stats and db_stats[0].get("total_bytes") is not None else 0
        except Exception as exc:
            logger.warning("Failed to fetch ClickHouse database size: %s", exc)
            total_bytes = 0

        try:
            active = self._query_dicts(
                """
                SELECT count() AS connections
                FROM system.processes
                WHERE is_initial_query = 1
                """
            )
            active_connections = int(active[0]["connections"]) if active else 0
        except Exception as exc:
            logger.warning("Failed to fetch ClickHouse active connections: %s", exc)
            active_connections = 0

        return {
            "total_db_size": total_bytes,
            "active_backends": active_connections,
        }
