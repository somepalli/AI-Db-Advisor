# app/services/ai_client.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import httpx
from ..config import settings

class LLMClient:
    def __init__(self, provider: str | None = None, model: str | None = None, endpoint: str | None = None):
        self.provider = provider or settings.LLM_PROVIDER
        self.model = model or settings.LLM_MODEL
        self.endpoint = (endpoint or settings.LLM_ENDPOINT).rstrip("/")

    def chat(self, messages: List[Dict[str, str]], json_response: bool = False, temperature: float = 0.2, max_tokens: int = 1500) -> str:
        """
        Currently supports Ollama's /api/chat.
        """
        if self.provider != "ollama":
            raise RuntimeError(f"Unsupported LLM provider: {self.provider}")

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        # Enable JSON mode for Ollama if json_response is True
        if json_response:
            payload["format"] = "json"

        url = f"{self.endpoint}/api/chat"
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            text = data.get("message", {}).get("content", "")

            if json_response:
                import json, re
                import logging
                logger = logging.getLogger(__name__)

                logger.info(f"Raw LLM text response:\n{text}")

                # Try to parse as direct JSON first
                try:
                    parsed = json.loads(text)
                    logger.info(f"Successfully parsed as direct JSON")
                    return parsed
                except json.JSONDecodeError:
                    logger.info("Failed direct JSON parse, trying regex extraction...")

                # Try to extract JSON from markdown code blocks
                code_block_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
                if code_block_match:
                    try:
                        parsed = json.loads(code_block_match.group(1))
                        logger.info(f"Successfully extracted JSON from code block")
                        return parsed
                    except json.JSONDecodeError:
                        logger.warning("Found code block but failed to parse JSON")

                # Try to find JSON object or array anywhere in the text
                # Match the outermost JSON structure
                json_match = re.search(r'(\{(?:[^{}]|(?1))*\})', text, re.DOTALL)
                if not json_match:
                    json_match = re.search(r'(\[(?:[^\[\]]|(?1))*\])', text, re.DOTALL)

                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                        logger.info(f"Successfully extracted JSON using regex")
                        return parsed
                    except json.JSONDecodeError as e:
                        logger.error(f"Regex found JSON-like structure but parsing failed: {e}")

                logger.error("All JSON extraction methods failed, returning raw text")
                return text

            return text
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM unreachable at {url}: {e}") from e
