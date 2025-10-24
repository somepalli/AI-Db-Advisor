import sys
import inspect
sys.path.insert(0, ".venv")

from app.services.duckdb_agent import DuckDBAgent

sig = inspect.signature(DuckDBAgent.create_table_from_schema)
print(f"Signature: {sig}")
print(f"Parameters: {list(sig.parameters.keys())}")
