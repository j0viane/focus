"""FOCUS_LLM_* environment knobs (opt-in, default off)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from focus.config import FocusConfig

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"


class LlmSettings(BaseSettings):
    """Loaded from env / ``.env``. Keys never appear in logs or HUD."""

    model_config = SettingsConfigDict(
        env_prefix="FOCUS_LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = False
    provider: Literal["openai", "anthropic", "ollama"] = "openai"
    api_key: str | None = None
    model: str | None = Field(
        default=None,
        description="Optional model id; provider default when unset.",
    )
    base_url: str | None = Field(
        default=None,
        description="OpenAI-compatible base URL (Ollama default when provider=ollama).",
    )
    concurrency: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Max parallel caption label requests (FOCUS_LLM_CONCURRENCY).",
    )


def load_llm_settings() -> LlmSettings:
    return LlmSettings()


def resolve_llm_captions(
    *,
    force: bool | None = None,
    overlays: dict[str, str] | None = None,
    config: FocusConfig | None = None,
) -> bool:
    """Whether this audit may call the caption labeler.

    Live overlays always skip. Opt-in for a run via ``--llm-captions`` /
    ``force=True``, or ``.focus.toml [llm] captions``.

    ``FOCUS_LLM_ENABLED`` alone does **not** turn captions on (that hung IDE
    autosave when paired with an older CLI that lacked ``--no-llm-captions``).
    Use ``--llm-captions`` or the extension ``focus.llmCaptions`` setting.
    """
    if overlays:
        return False
    if force is False:
        return False
    settings = load_llm_settings()
    if settings.provider != "ollama" and not (settings.api_key or "").strip():
        return False
    cfg = config or FocusConfig()
    if force is True:
        return True
    return bool(cfg.llm_captions)
