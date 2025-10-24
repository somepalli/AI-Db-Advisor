"""
MongoDB Agent
Supports MongoDB with AI-powered optimization
"""
from .base_agent import BaseAgent
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class MongoDBAgent(BaseAgent):
    """
    MongoDB database agent (NoSQL).
    Connection string format: mongodb://user:password@host:port/database
    or: mongodb+srv://user:password@cluster.mongodb.net/database
    """

    def get_db_type(self) -> str:
        return "mongodb"

    def _conn(self):
        """Create MongoDB connection using pymongo"""
        try:
            from pymongo import MongoClient
            return MongoClient(self.dsn)
        except ImportError:
            raise Exception("pymongo not installed. Run: pip install pymongo")

    def _get_db(self):
        """Get database from connection string"""
        from urllib.parse import urlparse
        parsed = urlparse(self.dsn)
        db_name = parsed.path.lstrip('/').split('?')[0] if parsed.path else 'test'

        client = self._conn()
        return client[db_name]

    def get_schema(self) -> Dict[str, Any]:
        """Get MongoDB schema (collections and sample fields)"""
        db = self._get_db()

        schema: Dict[str, Any] = {}

        for collection_name in db.list_collection_names():
            # Sample first document to infer schema
            sample_doc = db[collection_name].find_one()

            if sample_doc:
                fields = []
                for field_name, field_value in sample_doc.items():
                    field_type = type(field_value).__name__
                    fields.append({
                        "column": field_name,
                        "type": field_type,
                        "nullable": "YES"  # MongoDB fields are always optional by default
                    })

                schema[collection_name] = fields

        return {"tables": schema}  # Use "tables" for consistency, though they're collections

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get slow queries from MongoDB profiler"""
        db = self._get_db()

        try:
            # Enable profiling if not already enabled
            profile_level = db.command("profile", -1)
            logger.info(f"MongoDB profiling level: {profile_level}")

            # Get slow queries from system.profile
            slow_queries = list(db['system.profile'].find({
                "op": {"$in": ["query", "update", "remove"]},
                "millis": {"$gt": 100}  # Queries taking > 100ms
            }).sort("millis", -1).limit(limit))

            results = []
            for q in slow_queries:
                results.append({
                    "query": str(q.get("command", {})),
                    "calls": 1,
                    "mean_time_ms": q.get("millis", 0),
                    "rows": q.get("nreturned", 0),
                    "source": "profiler"
                })

            return results
        except Exception as e:
            logger.warning(f"Profiler unavailable: {e}")
            return []

    def explain(self, query_filter: str, collection: str = None, analyze: bool = False) -> Dict[str, Any]:
        """Get MongoDB explain plan"""
        db = self._get_db()

        try:
            # Parse query filter (should be JSON string)
            import json
            filter_dict = json.loads(query_filter) if isinstance(query_filter, str) else query_filter

            if not collection:
                # Try to infer collection from context
                collections = db.list_collection_names()
                collection = collections[0] if collections else None

            if not collection:
                return {"plan": None, "error": "No collection specified"}

            # Get explain plan
            explain_result = db[collection].find(filter_dict).explain()

            return {"plan": explain_result}
        except Exception as e:
            logger.error(f"EXPLAIN failed: {e}")
            return {"plan": None, "error": str(e)}

    def locks(self) -> List[Dict[str, Any]]:
        """Get MongoDB locks from currentOp"""
        db = self._get_db()

        try:
            admin_db = db.client.admin
            current_ops = admin_db.command("currentOp")

            locks = []
            for op in current_ops.get("inprog", []):
                if "locks" in op:
                    locks.append({
                        "locktype": "collection",
                        "mode": str(op.get("locks", {})),
                        "granted": op.get("waitingForLock", False) == False,
                        "pid": op.get("opid", 0)
                    })

            return locks
        except Exception as e:
            logger.warning(f"currentOp unavailable: {e}")
            return []

    def stats(self) -> Dict[str, Any]:
        """Get MongoDB database statistics"""
        db = self._get_db()

        try:
            db_stats = db.command("dbStats")

            return {
                "total_db_size": db_stats.get("dataSize", 0) + db_stats.get("indexSize", 0),
                "active_backends": db_stats.get("connections", {}).get("current", 0)
            }
        except Exception as e:
            logger.error(f"dbStats failed: {e}")
            return {"total_db_size": 0, "active_backends": 0}

    def get_existing_indexes(self, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing MongoDB indexes"""
        db = self._get_db()
        indexes = []

        collections = [collection_name] if collection_name else db.list_collection_names()

        for coll_name in collections:
            try:
                coll_indexes = db[coll_name].index_information()

                for idx_name, idx_info in coll_indexes.items():
                    # Extract field names from key
                    columns = [field[0] for field in idx_info.get("key", [])]

                    indexes.append({
                        "table_schema": db.name,
                        "table_name_short": coll_name,
                        "table_name": f"{db.name}.{coll_name}",
                        "index_name": idx_name,
                        "columns": columns,
                        "is_unique": idx_info.get("unique", False),
                        "index_type": "mongodb"
                    })
            except Exception as e:
                logger.warning(f"Could not get indexes for {coll_name}: {e}")

        return indexes

    def index_exists(self, collection_name: str, fields: List[str]) -> bool:
        """Check if MongoDB index exists"""
        existing = self.get_existing_indexes(collection_name)
        fields_normalized = [f.lower().strip() for f in fields]

        for idx in existing:
            idx_fields = [f.lower().strip() for f in idx['columns']]
            if fields_normalized == idx_fields[:len(fields_normalized)]:
                logger.info(f"Index already exists: {idx['index_name']} on {idx['table_name_short']}")
                return True

        return False

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get MongoDB-specific optimization context"""
        db = self._get_db()

        try:
            # Get server info
            server_info = db.client.server_info()
            version = server_info.get("version", "unknown")

            # Get collection count
            collection_count = len(db.list_collection_names())

            # Get total index count
            index_count = 0
            for coll in db.list_collection_names():
                index_count += len(db[coll].index_information())

            stats = self.stats()

            return {
                "db_type": "mongodb",
                "version": version,
                "total_size": stats.get("total_db_size", 0),
                "table_count": collection_count,  # Collections
                "index_count": index_count
            }
        except Exception as e:
            logger.error(f"get_optimization_context failed: {e}")
            return {
                "db_type": "mongodb",
                "version": "unknown",
                "total_size": 0,
                "table_count": 0,
                "index_count": 0
            }
