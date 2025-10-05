from typing import Dict, Any
from fastapi import HTTPException
from .config import settings
from .services.registry import get_agent_for

def resolve_agent(ds_id: str):
    cfg: Dict[str, Any] = settings.DATASOURCES.get(ds_id)
    if not cfg:
        # was: raise ValueError(...)
        raise HTTPException(status_code=404, detail=f"Unknown data_source: {ds_id}")
    try:
        return get_agent_for(cfg["engine"], cfg["dsn"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Datasource init failed: {e}")
