"""Decide when a deterministic caption is too weak to keep as the only ℹ️."""

from __future__ import annotations

import re

_STRONG_EDIT = re.compile(
    r"^(Added (a|\d+) blank lines?\.|"
    r"Adds imports? for |"
    r"Returns `|Sets `|Updates `|"
    r"Calls `|Adds this |Uses the node's name)",
    re.IGNORECASE,
)

_WEAK_MARKERS = (
    "other code may call",
    "on the call path to other modules",
    "see implementation",
    "is defined here",
    "changes what this function returns",
    "returns `none`",
    "returns none.",
    "automated test that",
    "instantiate or subclass",
    "client for talking to",
)


def is_weak_caption(detail: str, *, symbol_name: str = "") -> bool:
    """True when the ladder left us empty or with generic filler — LLM may try."""
    text = (detail or "").strip()
    if not text:
        return True
    if _STRONG_EDIT.match(text):
        # Plumbing call chrome with truncated names still counts as shaped for now.
        return False
    lower = text.lower()
    if any(marker in lower for marker in _WEAK_MARKERS):
        return True
    if symbol_name:
        human = _humanize_name(symbol_name)
        if human and lower.strip("` .") == human:
            return True
    # Curated purpose without edit shape is still a candidate when we have no slots.
    if text.startswith("`") and " — " in text:
        return True
    return False


def _humanize_name(name: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()
    words = [w for w in snake.strip("_").split("_") if w]
    return " ".join(words)
