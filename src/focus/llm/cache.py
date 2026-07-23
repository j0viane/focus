"""Disk + memory cache for validated LLM captions (pack fingerprint)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
from pathlib import Path
from typing import Any

from focus.llm.pack import CaptionEvidencePack

_LOCK = threading.Lock()
_MEMORY: dict[str, str] = {}
_MAX_MEMORY = 512
_CACHE_SUBDIR = "focus-llm-caption-cache"


def pack_fingerprint(pack: CaptionEvidencePack, *, model: str) -> str:
    """Stable hash of pack JSON + model id."""
    payload: dict[str, Any] = {
        "model": model,
        "pack": pack.model_dump(mode="json"),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get_cached_caption(key: str) -> str | None:
    with _LOCK:
        hit = _MEMORY.get(key)
        if hit is not None:
            return hit
    path = _disk_path(key)
    try:
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                with _LOCK:
                    _remember(key, text)
                return text
    except OSError:
        return None
    return None


def put_cached_caption(key: str, detail: str) -> None:
    text = (detail or "").strip()
    if not text:
        return
    with _LOCK:
        _remember(key, text)
    path = _disk_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    except OSError:
        return


def clear_caption_cache(*, disk: bool = False) -> None:
    """Test helper — wipe memory cache; optionally wipe temp disk files."""
    with _LOCK:
        _MEMORY.clear()
    if not disk:
        return
    root = Path(tempfile.gettempdir()) / _CACHE_SUBDIR
    try:
        if root.is_dir():
            for path in root.glob("*.txt"):
                try:
                    path.unlink()
                except OSError:
                    pass
    except OSError:
        return


def _remember(key: str, text: str) -> None:
    if key in _MEMORY:
        _MEMORY[key] = text
        return
    if len(_MEMORY) >= _MAX_MEMORY:
        # Drop an arbitrary oldest insertion (dict preserves order on 3.7+).
        _MEMORY.pop(next(iter(_MEMORY)))
    _MEMORY[key] = text


def _disk_path(key: str) -> Path:
    return Path(tempfile.gettempdir()) / _CACHE_SUBDIR / f"{key}.txt"
