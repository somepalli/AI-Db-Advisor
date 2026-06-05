from pydantic import BaseModel
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file in project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseModel):
    DATASOURCES: dict = {}  # Will be populated from persistence file
    ENV: str = os.getenv("ENV", "dev")

    # When running inside a container, a DSN host of localhost/127.0.0.1 points at the
    # container itself, not the user's machine. If enabled, such hosts are rewritten to
    # DSN_LOCALHOST_REPLACEMENT (host.docker.internal on Docker Desktop) at connect time,
    # so users can register datasources with the natural "localhost" host. Off by default;
    # docker-compose turns it on automatically.
    REWRITE_LOCALHOST_DSN: bool = os.getenv("REWRITE_LOCALHOST_DSN", "false").lower() == "true"
    DSN_LOCALHOST_REPLACEMENT: str = os.getenv("DSN_LOCALHOST_REPLACEMENT", "host.docker.internal")

    # LLM config — provider-agnostic: "ollama" (default), "openai" (OpenAI-compatible), "anthropic"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    LLM_ENDPOINT: str = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:11434")  # Ollama default
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")  # required for openai/anthropic cloud providers

    # MCP (Model Context Protocol) config
    MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "false").lower() == "true"
    MCP_ENDPOINT: str = os.getenv("MCP_ENDPOINT", "https://mcp.googleapis.com/v1")
    MCP_API_KEY: str = os.getenv("MCP_API_KEY", "")
    MCP_TIMEOUT: int = int(os.getenv("MCP_TIMEOUT", "30"))
    MCP_MAX_SUGGESTIONS: int = int(os.getenv("MCP_MAX_SUGGESTIONS", "5"))

    # Notification channel configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_TO: str = os.getenv("EMAIL_TO", "")
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

    # MCP Safety Settings (DO NOT CHANGE)
    MCP_AUTO_EXECUTE: bool = False  # MUST be False
    MCP_REQUIRE_APPROVAL: bool = True  # MUST be True

settings = Settings()

# Load datasources from persistence file
try:
    from .services.datasource_persistence import load_datasources
    settings.DATASOURCES = load_datasources()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to load datasources: {e}")


# Initialize MCP client if enabled
def initialize_mcp():
    """Initialize MCP client at application startup."""
    if settings.MCP_ENABLED:
        try:
            from .services.mcp_client import initialize_mcp_client
            mcp_client = initialize_mcp_client(
                endpoint=settings.MCP_ENDPOINT,
                api_key=settings.MCP_API_KEY or ""  # API key optional for local bridge
            )
            import logging
            logger = logging.getLogger(__name__)
            logger.info("MCP integration initialized successfully")
            return mcp_client
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to initialize MCP client: {e}")
            return None
    return None
