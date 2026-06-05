from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings
from ..services.ai_client import LLMClient
from ..services.llm_settings import update_llm_settings

router = APIRouter(prefix="/llm", tags=["llm"])


class LLMConfigUpdate(BaseModel):
    """Partial LLM config. Omitted/None fields are left unchanged."""
    provider: str | None = None
    model: str | None = None
    endpoint: str | None = None
    api_key: str | None = None


@router.get("/status")
def llm_status():
    """Report the configured LLM provider/model and whether it's reachable.

    Used by the UI to show, e.g., "🟢 Ollama · qwen2.5:7b-instruct" so users can
    see at a glance which LLM the app is talking to (and fix it if it's down)."""
    return LLMClient().status()


@router.get("/config")
def llm_config():
    """Return the current LLM config for the settings UI.

    The API key itself is never returned — only whether one is set — so the UI can
    show a "key saved" hint without leaking the secret."""
    return {
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "endpoint": settings.LLM_ENDPOINT,
        "has_api_key": bool(settings.LLM_API_KEY),
    }


@router.post("/test")
def llm_test(cfg: LLMConfigUpdate):
    """Probe a candidate config without saving it (the UI's "Test connection" button).

    Falls back to the saved value for any field the user left blank, so an empty API
    key reuses the stored one rather than wiping it."""
    client = LLMClient(
        provider=cfg.provider or settings.LLM_PROVIDER,
        model=cfg.model or settings.LLM_MODEL,
        endpoint=cfg.endpoint or settings.LLM_ENDPOINT,
        api_key=cfg.api_key if cfg.api_key else settings.LLM_API_KEY,
    )
    return client.status()


@router.put("/config")
def update_llm_config(cfg: LLMConfigUpdate):
    """Persist a new LLM config (applied immediately to all subsequent requests).

    Returns the live status so the UI can confirm the new connection right away. An
    empty/omitted ``api_key`` leaves the stored key untouched."""
    update_llm_settings(
        provider=cfg.provider,
        model=cfg.model,
        endpoint=cfg.endpoint,
        # Treat empty string as "leave unchanged" so saving other fields doesn't wipe the key.
        api_key=cfg.api_key if cfg.api_key else None,
    )
    return LLMClient().status()
