# app/services/ai_client.py
from __future__ import annotations
from typing import List, Dict, Any, Iterator
import json
import logging
import re
import httpx
from ..config import settings
from .dsn_utils import maybe_rewrite_localhost_url

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"


class LLMClient:
    """Provider-agnostic chat client.

    Supported providers (selected via LLM_PROVIDER):
      - "ollama"    : Ollama native /api/chat (default)
      - "openai"    : OpenAI-compatible /v1/chat/completions (OpenAI, Azure-style gateways,
                      LM Studio, llama.cpp, vLLM, Ollama's own /v1, etc.)
      - "anthropic" : Anthropic Claude /v1/messages

    All providers honour LLM_ENDPOINT / LLM_MODEL / LLM_API_KEY.
    """

    def __init__(self, provider: str | None = None, model: str | None = None,
                 endpoint: str | None = None, api_key: str | None = None):
        self.provider = (provider or settings.LLM_PROVIDER or "ollama").lower()
        self.model = model or settings.LLM_MODEL
        # In a container, a localhost endpoint (e.g. a host-run Ollama) must be
        # redirected to the host machine; no-op outside a container (flag off).
        self.endpoint = maybe_rewrite_localhost_url((endpoint or settings.LLM_ENDPOINT)).rstrip("/")
        self.api_key = api_key if api_key is not None else getattr(settings, "LLM_API_KEY", "")

    # -- public API ---------------------------------------------------------

    def chat(self, messages: List[Dict[str, str]], json_response: bool = False,
             temperature: float = 0.2, max_tokens: int = 1500, stream: bool = False):
        """Return the full completion text (stream=False) or a generator of text chunks
        (stream=True). When json_response is True the text is parsed into JSON if possible."""
        if self.provider == "ollama":
            return self._chat_ollama(messages, json_response, temperature, max_tokens, stream)
        if self.provider in ("openai", "openai-compatible"):
            return self._chat_openai(messages, json_response, temperature, max_tokens, stream)
        if self.provider == "anthropic":
            return self._chat_anthropic(messages, json_response, temperature, max_tokens, stream)
        raise RuntimeError(f"Unsupported LLM provider: {self.provider}")

    def status(self) -> Dict[str, Any]:
        """Lightweight health probe for the configured LLM, for UI display.

        Returns provider/model/endpoint plus a `connected` flag and a human `detail`.
        For Ollama it lists installed models and flags whether the configured model
        is present; for OpenAI-compatible it hits /v1/models; Anthropic is reported as
        configured when an API key is set (no free reachability probe)."""
        info: Dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "endpoint": self.endpoint,
            "connected": False,
            "models": [],
            "detail": "",
        }
        try:
            if self.provider == "ollama":
                with httpx.Client(timeout=5) as client:
                    resp = client.get(f"{self.endpoint}/api/tags")
                    resp.raise_for_status()
                    names = [m.get("name", "") for m in (resp.json().get("models") or [])]
                info["models"] = names
                info["connected"] = True
                if self.model in names:
                    info["detail"] = f"Connected to Ollama — model '{self.model}' ready"
                elif names:
                    info["detail"] = (
                        f"Connected to Ollama, but model '{self.model}' is not pulled. "
                        f"Run: ollama pull {self.model}"
                    )
                else:
                    info["detail"] = "Connected to Ollama, but no models are installed"
            elif self.provider in ("openai", "openai-compatible"):
                headers = self._openai_headers()
                base = self.endpoint
                url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
                with httpx.Client(timeout=5) as client:
                    resp = client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                info["models"] = [m.get("id", "") for m in (data.get("data") or [])]
                info["connected"] = True
                info["detail"] = f"Connected to {self.provider} — model '{self.model}'"
            elif self.provider == "anthropic":
                info["connected"] = bool(self.api_key)
                info["detail"] = (
                    f"Anthropic configured — model '{self.model}'"
                    if self.api_key else "Anthropic selected but no API key set (LLM_API_KEY)"
                )
            else:
                info["detail"] = f"Unknown provider '{self.provider}'"
        except Exception as e:
            info["connected"] = False
            info["detail"] = f"Not reachable at {self.endpoint}: {e}"
        return info

    # -- ollama -------------------------------------------------------------

    def _chat_ollama(self, messages, json_response, temperature, max_tokens, stream):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_response:
            payload["format"] = "json"
        url = f"{self.endpoint}/api/chat"

        if stream:
            return self._stream(url, payload, headers=None, extract=self._ollama_delta)

        data = self._post(url, payload, headers=None)
        text = data.get("message", {}).get("content", "")
        return self._maybe_json(text, json_response)

    @staticmethod
    def _ollama_delta(chunk: dict) -> tuple[str, bool]:
        content = chunk.get("message", {}).get("content", "") if "message" in chunk else ""
        return content, bool(chunk.get("done", False))

    # -- openai-compatible --------------------------------------------------

    def _openai_url(self) -> str:
        base = self.endpoint
        return f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"

    def _openai_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _chat_openai(self, messages, json_response, temperature, max_tokens, stream):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if json_response:
            payload["response_format"] = {"type": "json_object"}
        url = self._openai_url()
        headers = self._openai_headers()

        if stream:
            return self._stream_sse(url, payload, headers, extract=self._openai_sse_delta)

        data = self._post(url, payload, headers)
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        return self._maybe_json(text, json_response)

    @staticmethod
    def _openai_sse_delta(obj: dict) -> str:
        return ((obj.get("choices") or [{}])[0].get("delta", {}) or {}).get("content", "") or ""

    # -- anthropic ----------------------------------------------------------

    def _anthropic_url(self) -> str:
        base = self.endpoint
        return f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"

    @staticmethod
    def _split_system(messages: List[Dict[str, str]]) -> tuple[str, list]:
        system_parts, convo = [], []
        for m in messages:
            if m.get("role") == "system":
                system_parts.append(m.get("content", ""))
            else:
                convo.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        return "\n\n".join(p for p in system_parts if p), convo

    def _chat_anthropic(self, messages, json_response, temperature, max_tokens, stream):
        system, convo = self._split_system(messages)
        if json_response:
            system = (system + "\n\n" if system else "") + "Respond with ONLY valid JSON, no prose."
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": convo,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        url = self._anthropic_url()

        if stream:
            return self._stream_sse(url, payload, headers, extract=self._anthropic_sse_delta)

        data = self._post(url, payload, headers)
        text = "".join(
            block.get("text", "") for block in (data.get("content") or []) if block.get("type") == "text"
        )
        return self._maybe_json(text, json_response)

    @staticmethod
    def _anthropic_sse_delta(obj: dict) -> str:
        if obj.get("type") == "content_block_delta":
            return (obj.get("delta", {}) or {}).get("text", "") or ""
        return ""

    # -- transport helpers --------------------------------------------------

    def _post(self, url: str, payload: dict, headers: dict | None) -> dict:
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response is not None else ""
            raise RuntimeError(f"LLM request failed ({e.response.status_code}) at {url}: {body}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM unreachable at {url}: {e}") from e

    def _stream(self, url: str, payload: dict, headers: dict | None, extract) -> Iterator[str]:
        """Newline-delimited JSON streaming (Ollama)."""
        try:
            with httpx.Client(timeout=120) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse streaming chunk: {line}")
                            continue
                        content, done = extract(chunk)
                        if content:
                            yield content
                        if done:
                            break
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM streaming failed at {url}: {e}") from e

    def _stream_sse(self, url: str, payload: dict, headers: dict, extract) -> Iterator[str]:
        """Server-Sent-Events streaming (OpenAI / Anthropic)."""
        try:
            with httpx.Client(timeout=120) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        content = extract(obj)
                        if content:
                            yield content
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM streaming failed at {url}: {e}") from e

    # -- shared JSON extraction --------------------------------------------

    @staticmethod
    def _maybe_json(text: str, json_response: bool):
        """Return parsed JSON when json_response is requested and the text contains JSON,
        otherwise the raw text. Mirrors the previous Ollama-mode parsing fallbacks."""
        if not json_response:
            return text

        logger.info(f"Raw LLM text response:\n{text}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        code_block = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                logger.warning("Found code block but failed to parse JSON")

        # Best-effort: take the span from the first opening to the last matching
        # closing bracket. (stdlib `re` has no recursive-subpattern support.)
        for open_c, close_c in (("{", "}"), ("[", "]")):
            start, end = text.find(open_c), text.rfind(close_c)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue

        logger.error("All JSON extraction methods failed, returning raw text")
        return text
