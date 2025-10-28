from fastapi import APIRouter, HTTPException
from ..schemas import DataSourceCreate
from ..config import settings
from ..services.registry import get_supported_engines

router = APIRouter(prefix="/datasources", tags=["datasources"])

@router.post("", status_code=201)
def register_ds(ds: DataSourceCreate):
    if ds.id in settings.DATASOURCES:
        raise HTTPException(409, "data_source id already exists")
    settings.DATASOURCES[ds.id] = {"engine": ds.engine, "dsn": ds.dsn}
    return {"ok": True, "id": ds.id}

@router.get("")
def list_ds():
    return {"items": [{"id": k, **v} for k, v in settings.DATASOURCES.items()]}

@router.delete("/{ds_id}", status_code=200)
def delete_ds(ds_id: str):
    """Delete a data source by ID"""
    if ds_id not in settings.DATASOURCES:
        raise HTTPException(404, f"Data source '{ds_id}' not found")

    del settings.DATASOURCES[ds_id]
    return {"ok": True, "message": f"Data source '{ds_id}' deleted successfully"}

@router.get("/engines")
def list_supported_engines():
    """Get list of all supported database engines"""
    engines = get_supported_engines()

    # Group by database type
    db_types = {
        "PostgreSQL": ["postgres", "postgresql", "pg"],
        "MySQL/MariaDB": ["mysql", "mariadb"],
        "SQL Server": ["sqlserver", "mssql", "sql-server"],
        "Oracle Database": ["oracle", "oracle-db"],
        "MongoDB": ["mongodb", "mongo"],
        "Redis": ["redis"],
        "SQLite": ["sqlite", "sqlite3"],
        "Cassandra": ["cassandra", "cassandra-db"],
        "ClickHouse": ["clickhouse", "clickhouse+http", "clickhouse+https"],
    }

    return {
        "engines": engines,
        "grouped": db_types,
        "count": len(set(engines))
    }
