"""Unsaved editor buffers as analysis overlays (no disk writes).

The IDE can pass dirty file text so ``focus audit --local`` sees what the
author is looking at — not only what is already saved on disk.
"""

from __future__ import annotations

import difflib
import json
import subprocess
from pathlib import Path

from focus.ingest.diff import resolve_base_ref
from focus.models import ModuleFacts
from focus.scan.parser import parse_source
from focus.scan.walker import SOURCE_EXTENSIONS


def load_overlay_file(path: Path) -> dict[str, str]:
    """Load ``{repo_relative_path: full_file_text}`` from a JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("overlay file must be a JSON object of path → text")
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("overlay entries must be string path → string text")
        rel = key.replace("\\", "/").lstrip("./")
        if not rel or rel.startswith(".."):
            continue
        out[rel] = value
    return out


def line_ranges_from_texts(base_text: str, overlay_text: str) -> list[tuple[int, int]]:
    """1-based inclusive new/changed line ranges (overlay side) vs base text."""
    base_lines = base_text.splitlines()
    overlay_lines = overlay_text.splitlines()
    matcher = difflib.SequenceMatcher(a=base_lines, b=overlay_lines, autojunk=False)
    spans: list[tuple[int, int]] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace") and j1 < j2:
            # difflib indices are 0-based; convert to 1-based inclusive.
            spans.append((j1 + 1, j2))
    return _coalesce(spans)


def git_blob_text(root: Path, base: str, rel: str) -> str:
    """Contents of ``rel`` at ``base``, or empty string if the file is new."""
    from focus.ingest.diff import GitDiffError

    root = root.resolve()
    try:
        resolved = resolve_base_ref(root, base)
    except GitDiffError:
        return ""
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{resolved}:{rel}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def apply_overlays(
    root: Path,
    base: str,
    *,
    overlays: dict[str, str],
    changed_paths: list[str],
    source_paths: list[str],
    line_ranges: dict[str, list[tuple[int, int]]],
    facts_by_path: dict[str, ModuleFacts],
) -> tuple[list[str], list[str], dict[str, list[tuple[int, int]]], dict[str, ModuleFacts]]:
    """Merge overlays into audit inputs. Overlay wins for ranges + facts."""
    if not overlays:
        return changed_paths, source_paths, line_ranges, facts_by_path

    root = root.resolve()
    changed = set(changed_paths)
    sources = set(source_paths)
    ranges = {k: list(v) for k, v in line_ranges.items()}
    facts = dict(facts_by_path)

    for rel, text in overlays.items():
        suffix = Path(rel).suffix.lower()
        if suffix not in SOURCE_EXTENSIONS:
            continue
        base_text = git_blob_text(root, base, rel)
        if text == base_text and rel not in changed:
            # Buffer matches base and git already ignores it — nothing to add.
            continue
        spans = line_ranges_from_texts(base_text, text)
        if not spans and text != base_text:
            # Pure deletion vs base can leave empty new-side ranges; keep a sentinel
            # so the file stays in the changed set when the buffer still differs.
            spans = [(1, max(1, len(text.splitlines())))] if text.strip() else []
        ranges[rel] = spans
        path = root / rel
        facts[rel] = parse_source(text.encode("utf-8"), path)
        changed.add(rel)
        sources.add(rel)

    return sorted(changed), sorted(sources), ranges, facts


def _coalesce(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged
