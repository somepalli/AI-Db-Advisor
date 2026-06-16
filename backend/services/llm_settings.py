"""
Runtime-configurable LLM settings.

The LLM connection (provider / model / endpoint / API key) can be changed from the
UI at runtime instead of editing the .env file. Overrides are persisted to a JSON
file so they survive restarts, and overlaid on top of the env-derived defaults in
``settings`` at startup. Every request builds a fresh ``LLMClient()`` from
``settings``, so an update takes effect immediately for all subsequent calls.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import settings

logger = logging.getLogger(__name__)

# Persist next to datasources.json by default; Docker points this at the /data volume.
LLM_SETTINGS_FILE = Path(
    os.getenv("LLM_SETTINGS_FILE") or (Path(__file__).parent.parent / "llm_settings.json")
)

# Settings fields we allow the UI to override.
_FIELDS = ("LLM_PROVIDER", "LLM_MODEL", "LLM_FALLBACK_MODEL", "LLM_ENDPOINT", "LLM_API_KEY", "LLM_PROVIDER_TRUST")


def resolve_provider_trust() -> str:
    """Resolve the effective data-access trust: 'local' or 'hosted'.

    An explicit ``LLM_PROVIDER_TRUST`` override wins; otherwise it derives from the
    provider — only on-box Ollama is trusted as 'local', every hosted API is 'hosted'.
    The gated tool layer (services/tool_registry.py) keys data-tool access off this."""
    override = (getattr(settings, "LLM_PROVIDER_TRUST", "") or "").strip().lower()
    if override in ("local", "hosted"):
        return override
    return "local" if (settings.LLM_PROVIDER or "").lower() == "ollama" else "hosted"


def load_llm_settings() -> Dict[str, Any]:
    """Return persisted overrides, or an empty dict if none/unreadable."""
    try:
        if LLM_SETTINGS_FILE.exists():
            with open(LLM_SETTINGS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load LLM settings: {e}", exc_info=True)
    return {}


def save_llm_settings(data: Dict[str, Any]) -> None:
    """Persist overrides to the JSON file."""
    try:
        with open(LLM_SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved LLM settings to {LLM_SETTINGS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save LLM settings: {e}", exc_info=True)


def apply_persisted_llm_settings() -> None:
    """Overlay persisted overrides onto the in-memory ``settings`` (called at startup)."""
    data = load_llm_settings()
    for key in _FIELDS:
        value = data.get(key)
        if value is not None:
            setattr(settings, key, value)
    if data:
        logger.info(
            "Applied persisted LLM settings: provider=%s, model=%s, endpoint=%s",
            settings.LLM_PROVIDER, settings.LLM_MODEL, settings.LLM_ENDPOINT,
        )


def update_llm_settings(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    provider_trust: Optional[str] = None,
) -> Dict[str, Any]:
    """Update the in-memory ``settings`` and persist. ``None`` means 'leave unchanged'."""
    data = load_llm_settings()
    changes = {
        "LLM_PROVIDER": provider,
        "LLM_MODEL": model,
        "LLM_ENDPOINT": endpoint,
        "LLM_API_KEY": api_key,
        "LLM_PROVIDER_TRUST": provider_trust,
    }
    for key, value in changes.items():
        if value is not None:
            setattr(settings, key, value)
            data[key] = value
    save_llm_settings(data)
    return data
