"""File-hash keyed parse cache for ModuleFacts.

Unchanged source bytes reuse the last Tree-sitter extraction. The cache
stores derived facts only (safe to delete). Layout::

    <root>/.focus-cache/v1/<sha256>.json

``CACHE_SCHEMA_VERSION`` is part of the path so parser upgrades miss
stale entries instead of loading incompatible JSON.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from focus.models import ModuleFacts
from focus.scan.parser import parse_source

CACHE_DIR_NAME = ".focus-cache"
CACHE_SCHEMA_VERSION = "v1"


def cache_dir_for(root: Path) -> Path:
    """Return ``<root>/.focus-cache``."""
    return root.resolve() / CACHE_DIR_NAME


def content_hash(source: bytes) -> str:
    """SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(source).hexdigest()


def cache_path(cache_dir: Path, digest: str) -> Path:
    """Path for one content-addressed cache entry."""
    return cache_dir / CACHE_SCHEMA_VERSION / f"{digest}.json"


def load_facts(cache_dir: Path, digest: str, path: Path) -> ModuleFacts | None:
    """Load cached facts for ``digest``, rewriting ``path`` to the current file."""
    entry = cache_path(cache_dir, digest)
    if not entry.is_file():
        return None
    try:
        payload = json.loads(entry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema") != CACHE_SCHEMA_VERSION:
        return None
    try:
        facts = ModuleFacts.model_validate(payload["facts"])
    except Exception:
        return None
    return facts.model_copy(update={"path": path})


def store_facts(cache_dir: Path, digest: str, facts: ModuleFacts) -> None:
    """Persist facts under ``digest`` (best-effort; failures are ignored)."""
    entry = cache_path(cache_dir, digest)
    try:
        entry.parent.mkdir(parents=True, exist_ok=True)
        # Store path as posix string so JSON round-trips cleanly.
        serializable = facts.model_dump(mode="json")
        payload = {"schema": CACHE_SCHEMA_VERSION, "facts": serializable}
        entry.write_text(json.dumps(payload, indent=None, sort_keys=True), encoding="utf-8")
    except OSError:
        return


def parse_module_cached(
    path: Path,
    *,
    cache_dir: Path | None = None,
    use_cache: bool = True,
) -> ModuleFacts:
    """Parse ``path``, using ``cache_dir`` when ``use_cache`` is true."""
    source = path.read_bytes()
    if not use_cache or cache_dir is None:
        return parse_source(source, path)

    digest = content_hash(source)
    cached = load_facts(cache_dir, digest, path)
    if cached is not None:
        return cached

    facts = parse_source(source, path)
    store_facts(cache_dir, digest, facts)
    return facts
