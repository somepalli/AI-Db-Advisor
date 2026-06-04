from fastapi import APIRouter, HTTPException, BackgroundTasks
from ..schemas import DataSourceCreate
from ..config import settings
from ..services.registry import get_supported_engines
from ..services.datasource_persistence import save_datasources
from ..services.suggestion_store import suggestion_store
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasources", tags=["datasources"])

@router.post("", status_code=201)
async def register_ds(ds: DataSourceCreate, background_tasks: BackgroundTasks):
    if ds.id in settings.DATASOURCES:
        raise HTTPException(409, "data_source id already exists")
    suggestion_store.clear_for_datasource(ds.id)
    settings.DATASOURCES[ds.id] = {"engine": ds.engine, "dsn": ds.dsn}

    # Save to persistence file
    save_datasources(settings.DATASOURCES)

    # Start monitoring the new datasource automatically
    try:
        from ..services.monitoring_service import get_monitoring_service
        from ..routers.alerts import alert_engine

        monitoring_service = get_monitoring_service(alert_engine)
        await monitoring_service.start_monitoring_datasource(ds.id, ds.engine)
        logger.info(f"✅ Started monitoring for datasource: {ds.id}")
    except Exception as e:
        logger.error(f"Failed to start monitoring for {ds.id}: {e}", exc_info=True)
        # Don't fail the registration if monitoring fails

    return {"ok": True, "id": ds.id}

@router.get("")
def list_ds():
    return {"items": [{"id": k, **v} for k, v in settings.DATASOURCES.items()]}

@router.delete("/{ds_id}", status_code=200)
async def delete_ds(ds_id: str):
    """Delete a data source by ID"""
    if ds_id not in settings.DATASOURCES:
        raise HTTPException(404, f"Data source '{ds_id}' not found")

    # Stop monitoring the datasource
    try:
        from ..services.monitoring_service import get_monitoring_service
        from ..routers.alerts import alert_engine

        monitoring_service = get_monitoring_service(alert_engine)
        await monitoring_service.stop_monitoring_datasource(ds_id)
        logger.info(f"✅ Stopped monitoring for datasource: {ds_id}")
    except Exception as e:
        logger.error(f"Failed to stop monitoring for {ds_id}: {e}", exc_info=True)

    suggestion_store.clear_for_datasource(ds_id)
    del settings.DATASOURCES[ds_id]

    # Save to persistence file
    save_datasources(settings.DATASOURCES)

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
        "DuckDB": ["duckdb"],
    }

    return {
        "engines": engines,
        "grouped": db_types,
        "count": len(set(engines))
    }
