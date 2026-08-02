"""Smart triggers — full HUD vs pass-through for an audit change set.

Implements the Phase 2 cut of docs/TRIGGERS.md:
- Path rules (API, migrations, models, config) → diagram
- Shared utils/lib/common seeds → diagram
- Blast radius (≥ 2 downstream files) → diagram
- Docs/CSS/test-only with no production impact → pass-through
- ROA: tiny diff + low blast radius → pass-through (Phase 4b)
"""

from __future__ import annotations

from pathlib import PurePosixPath

from focus.hud.classify import is_danger_zone

# ROA: few changed lines + quiet impact → skip Mermaid (docs/TRIGGERS.md).
TINY_DIFF_MAX_LINES = 5
# "Low" blast for the tiny-diff rule — fewer than this many downstream files.
TINY_DIFF_MAX_DOWNSTREAM_FILES = 2

_PASS_SUFFIXES = frozenset({".md", ".markdown", ".rst", ".txt", ".css", ".scss", ".sass"})
_PASS_DIR_PREFIXES = ("docs/", ".github/")

_DIAGRAM_FRAGMENTS = (
    "/migrations/",
    "/routes/",
    "/api/",
    "/routers/",
    "/models/",
    "/utils/",
    "/lib/",
    "/common/",
)
_DIAGRAM_NAMES = frozenset(
    {
        "models.py",
        "schema.prisma",
        "settings.py",
        "config.py",
        "pyproject.toml",
        "requirements.txt",
        "poetry.lock",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "docker-compose.yml",
        "Dockerfile",
        ".env.example",
    }
)


def count_changed_lines(line_ranges: dict[str, list[tuple[int, int]]]) -> int:
    """Sum inclusive (start, end) spans — how big is this diff in new/changed lines?"""
    total = 0
    for spans in line_ranges.values():
        for start, end in spans:
            if end >= start:
                total += end - start + 1
    return total


def should_emit_diagram(
    *,
    changed_paths: list[str],
    python_seeds: list[str],
    has_downstream: bool,
    downstream_file_count: int = 0,
    graph=None,
    fan_out_threshold: int | None = None,
    changed_line_count: int | None = None,
) -> bool:
    """Return True when the change set warrants a full Focus HUD + Mermaid."""
    if not changed_paths or not python_seeds:
        return False

    # Test-only Python → pass-through (no production import surface in the seed set).
    if all(_is_test_path(path) for path in python_seeds):
        return False

    danger_kwargs = {}
    if fan_out_threshold is not None:
        danger_kwargs["fan_out_threshold"] = fan_out_threshold

    # Layer 1 / 4 — path Danger Zone or TRIGGERS path rule on a seed.
    if any(hits_diagram_path_rule(path) for path in python_seeds):
        return True
    if any(is_danger_zone(path, graph, **danger_kwargs) for path in python_seeds):
        return True

    # Shared package layouts always get a diagram when touched.
    if any(_is_shared_layout(path) for path in python_seeds):
        return True

    # ROA — tiny + low blast (no path/Danger/shared above) → pass-through.
    # Example: 1-line tweak in billing/service.py with a single importer.
    if (
        changed_line_count is not None
        and changed_line_count <= TINY_DIFF_MAX_LINES
        and downstream_file_count < TINY_DIFF_MAX_DOWNSTREAM_FILES
    ):
        return False

    # Layer 3 — blast radius: ≥ 2 downstream files (TRIGGERS.md default).
    if downstream_file_count >= 2:
        return True

    # One downstream file still warrants a diagram when the diff is not tiny.
    if has_downstream:
        return True

    return False


def hits_diagram_path_rule(path: str) -> bool:
    """True when TRIGGERS.md Layer 1 says this path warrants a diagram."""
    posix = PurePosixPath(path)
    if posix.name in _DIAGRAM_NAMES:
        return True
    padded = f"/{path.replace(chr(92), '/')}"
    return any(fragment in padded for fragment in _DIAGRAM_FRAGMENTS)


def is_pass_through_path(path: str) -> bool:
    """True for docs/style paths that never need a diagram by themselves."""
    posix = PurePosixPath(path)
    if posix.suffix.lower() in _PASS_SUFFIXES:
        return True
    lowered = path.replace("\\", "/").lower()
    return any(lowered.startswith(prefix) for prefix in _PASS_DIR_PREFIXES)


def _is_test_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return (
        lowered.startswith("tests/")
        or "/tests/" in lowered
        or PurePosixPath(path).name.startswith("test_")
    )


def _is_shared_layout(path: str) -> bool:
    padded = f"/{path.replace(chr(92), '/')}"
    return any(fragment in padded for fragment in ("/utils/", "/lib/", "/common/"))
