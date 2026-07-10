"""Smart triggers — full HUD vs pass-through for an audit change set.

Rules follow docs/TRIGGERS.md with a Phase 2 bias: skip diagrams for
non-code / docs-only changes; always diagram when a Danger Zone path is
touched or any Python file has downstream dependents.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from focus.hud.classify import is_danger_zone

_PASS_SUFFIXES = frozenset({".md", ".markdown", ".rst", ".txt", ".css", ".scss", ".sass"})
_PASS_DIR_PREFIXES = ("docs/", ".github/", "licenses/")


def should_emit_diagram(
    *,
    changed_paths: list[str],
    python_seeds: list[str],
    has_downstream: bool,
) -> bool:
    """Return True when the change set warrants a full Focus HUD + Mermaid."""
    if not changed_paths:
        return False
    if not python_seeds:
        return False
    if any(is_danger_zone(path) for path in python_seeds):
        return True
    if has_downstream:
        return True
    # Python changed but nothing depends on it and it is not a Danger Zone.
    return False


def is_pass_through_path(path: str) -> bool:
    """True for docs/style paths that never need a diagram by themselves."""
    posix = PurePosixPath(path)
    if posix.suffix.lower() in _PASS_SUFFIXES:
        return True
    lowered = path.replace("\\", "/").lower()
    return any(lowered.startswith(prefix) for prefix in _PASS_DIR_PREFIXES)
