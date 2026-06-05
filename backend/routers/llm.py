from fastapi import APIRouter
from ..services.ai_client import LLMClient

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/status")
def llm_status():
    """Report the configured LLM provider/model and whether it's reachable.

    Used by the UI to show, e.g., "🟢 Ollama · qwen2.5:7b-instruct" so users can
    see at a glance which LLM the app is talking to (and fix it if it's down)."""
    return LLMClient().status()
