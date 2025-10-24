"""
Redis Agent
Supports Redis with AI-powered optimization
"""
from .base_agent import BaseAgent
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RedisAgent(BaseAgent):
    """
    Redis database agent (NoSQL key-value store).
    Connection string format: redis://host:port/db
    or: redis://user:password@host:port/db
    """

    def get_db_type(self) -> str:
        return "redis"

    def _conn(self):
        """Create Redis connection using redis-py"""
        try:
            import redis
            from urllib.parse import urlparse

            parsed = urlparse(self.dsn)

            # Extract database number from path
            db = 0
            if parsed.path and len(parsed.path) > 1:
                try:
                    db = int(parsed.path.lstrip('/'))
                except ValueError:
                    db = 0

            return redis.Redis(
                host=parsed.hostname or 'localhost',
                port=parsed.port or 6379,
                db=db,
                password=parsed.password,
                decode_responses=True
            )
        except ImportError:
            raise Exception("redis not installed. Run: pip install redis")

    def get_schema(self) -> Dict[str, Any]:
        """Get Redis schema (key patterns and types)"""
        r = self._conn()

        try:
            # Sample keys to infer patterns
            sample_size = 100
            cursor = 0
            keys_sample = []

            # Scan keys (safer than KEYS *)
            for _ in range(10):  # Limit scan iterations
                cursor, keys = r.scan(cursor, count=sample_size)
                keys_sample.extend(keys)
                if cursor == 0:
                    break

            # Group by key patterns
            patterns: Dict[str, List[Dict[str, str]]] = {}

            for key in keys_sample[:sample_size]:
                key_type = r.type(key)

                # Extract pattern (before first number or colon)
                pattern = key.split(':')[0] if ':' in key else key.split('_')[0]

                patterns.setdefault(pattern, []).append({
                    "column": key,
                    "type": key_type,
                    "nullable": "YES"  # Redis keys are always optional
                })

            return {"tables": patterns}
        finally:
            r.close()

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get Redis slowlog"""
        r = self._conn()

        try:
            slowlog = r.slowlog_get(limit)

            results = []
            for entry in slowlog:
                # entry is a dict with: id, start_time, duration, command
                results.append({
                    "query": ' '.join(str(arg) for arg in entry.get('command', [])),
                    "calls": 1,
                    "mean_time_ms": entry.get('duration', 0) / 1000,  # Convert microseconds to ms
                    "rows": 0,
                    "source": "slowlog"
                })

            return results
        except Exception as e:
            logger.warning(f"SLOWLOG unavailable: {e}")
            return []
        finally:
            r.close()

    def explain(self, query_filter: str, analyze: bool = False) -> Dict[str, Any]:
        """Redis doesn't have EXPLAIN - return command info"""
        r = self._conn()

        try:
            # Parse command from query_filter
            parts = query_filter.strip().split()
            if not parts:
                return {"plan": None, "error": "No command specified"}

            command = parts[0].upper()

            # Get command info
            command_info = r.command_info(command)

            return {
                "plan": {
                    "command": command,
                    "info": command_info.get(command.lower(), {}) if command_info else {},
                    "note": "Redis does not support EXPLAIN. Command info shown instead."
                },
                "format": "redis"
            }
        except Exception as e:
            logger.error(f"Command info failed: {e}")
            return {"plan": None, "error": str(e)}
        finally:
            r.close()

    def locks(self) -> List[Dict[str, Any]]:
        """Redis doesn't have traditional locks - return client list"""
        r = self._conn()

        try:
            clients = r.client_list()

            locks = []
            for client in clients:
                if client.get('cmd', '') != 'client':  # Exclude our own client list command
                    locks.append({
                        "locktype": "client",
                        "mode": client.get('cmd', 'N/A'),
                        "granted": True,
                        "pid": client.get('id', 0),
                        "database_name": f"db{client.get('db', 0)}"
                    })

            return locks
        except Exception as e:
            logger.warning(f"CLIENT LIST unavailable: {e}")
            return []
        finally:
            r.close()

    def stats(self) -> Dict[str, Any]:
        """Get Redis statistics"""
        r = self._conn()

        try:
            info = r.info()

            return {
                "total_db_size": info.get('used_memory', 0),
                "active_backends": info.get('connected_clients', 0)
            }
        except Exception as e:
            logger.error(f"INFO failed: {e}")
            return {"total_db_size": 0, "active_backends": 0}
        finally:
            r.close()

    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Redis doesn't have indexes in traditional sense - return empty list"""
        return []

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Redis doesn't support indexes - always return False"""
        return False

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get Redis-specific optimization context"""
        r = self._conn()

        try:
            info = r.info()

            # Get key count across all DBs
            total_keys = 0
            for db_num in range(16):  # Redis default has 16 databases
                r.select(db_num)
                total_keys += r.dbsize()

            stats = self.stats()

            return {
                "db_type": "redis",
                "version": info.get('redis_version', 'unknown'),
                "total_size": stats.get("total_db_size", 0),
                "table_count": total_keys,  # Use key count as "table count"
                "index_count": 0  # Redis doesn't have traditional indexes
            }
        finally:
            r.close()
