from pydantic import BaseModel
import os


class Settings(BaseModel):
    DATASOURCES: dict = {}
    ENV: str = os.getenv("ENV", "dev")

    # LLM config (open-source via Ollama)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")  # "ollama" (default)
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    LLM_ENDPOINT: str = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:11434")  # Ollama default

settings = Settings()
