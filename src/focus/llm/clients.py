"""HTTP clients for OpenAI-compatible, Ollama, and Anthropic caption APIs."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import httpx

from focus.llm.settings import DEFAULT_OLLAMA_BASE_URL, LlmSettings

log = logging.getLogger("focus.llm")

SYSTEM_PROMPT = (
    "One sentence ≤110 chars. Use only facts in the pack. "
    "Do not invent callers, files, or behavior. Prefer measured slots. "
    "If unsure, restate deterministic_caption. "
    'Respond with JSON only: {"detail": "..."}'
)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class LabelClient(Protocol):
    def label(self, pack_json: dict[str, Any]) -> str | None: ...


def build_client(settings: LlmSettings) -> LabelClient | None:
    if settings.provider == "ollama":
        base = (settings.base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        return OpenAIClient(
            api_key=(settings.api_key or "ollama").strip() or "ollama",
            model=settings.model or DEFAULT_OLLAMA_MODEL,
            base_url=base,
        )
    key = (settings.api_key or "").strip()
    if not key:
        return None
    if settings.provider == "anthropic":
        return AnthropicClient(api_key=key, model=settings.model or DEFAULT_ANTHROPIC_MODEL)
    base = (settings.base_url or DEFAULT_OPENAI_BASE_URL).rstrip("/")
    return OpenAIClient(
        api_key=key,
        model=settings.model or DEFAULT_OPENAI_MODEL,
        base_url=base,
    )


class OpenAIClient:
    """OpenAI chat completions — also used for Ollama's OpenAI-compatible API."""

    def __init__(self, *, api_key: str, model: str, base_url: str = DEFAULT_OPENAI_BASE_URL) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def label(self, pack_json: dict[str, Any]) -> str | None:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(pack_json)},
            ],
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return _detail_from_content(content)
        except Exception as exc:  # noqa: BLE001 — never block audit
            log.debug("OpenAI-compatible caption label failed: %s", type(exc).__name__)
            return None


class AnthropicClient:
    def __init__(self, *, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def label(self, pack_json: dict[str, Any]) -> str | None:
        body = {
            "model": self.model,
            "max_tokens": 128,
            "temperature": 0,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": json.dumps(pack_json)},
            ],
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
            parts = data.get("content") or []
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            return _detail_from_content(text)
        except Exception as exc:  # noqa: BLE001 — never block audit
            log.debug("Anthropic caption label failed: %s", type(exc).__name__)
            return None


def _detail_from_content(content: str) -> str | None:
    if not content or not content.strip():
        return None
    text = content.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Model sometimes wraps JSON in fences.
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(parsed, dict):
        return None
    detail = parsed.get("detail")
    return detail if isinstance(detail, str) else None
