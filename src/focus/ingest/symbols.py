"""Map git diff hunks to changed Python definitions (symbol seeds).

Blast radius is still file-level in the graph. Symbol detection answers a
narrower question: *which defs in the changed files did the diff actually
touch?* That powers clearer HUD summaries and comments-only pass-through.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from focus.ingest.diff import DiffMode, GitDiffError, resolve_base_ref
from focus.models import Definition, ModuleFacts
from focus.scan import parse_module
from focus.scan.walker import SOURCE_EXTENSIONS

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class ChangedSymbol:
    """A definition whose source lines intersect the diff."""

    path: str
    name: str
    kind: str
    line: int


def changed_line_ranges(
    root: Path, base: str = "main", *, mode: DiffMode = "local"
) -> dict[str, list[tuple[int, int]]]:
    """New/changed line ranges per file (1-based, inclusive), from unified diffs."""
    root = root.resolve()
    resolved = resolve_base_ref(root, base)
    ranges: dict[str, list[tuple[int, int]]] = {}
    if mode == "range":
        _merge_ranges(
            ranges,
            _parse_diff(
                _git_diff(root, ["diff", "-U0", "--diff-filter=ACMR", f"{resolved}...HEAD"])
            ),
        )
    else:
        for args in (
            ["diff", "-U0", "--diff-filter=ACMR", resolved],
            ["diff", "-U0", "--cached", "--diff-filter=ACMR", resolved],
        ):
            _merge_ranges(ranges, _parse_diff(_git_diff(root, args)))
        untracked = _git_lines(root, ["ls-files", "--others", "--exclude-standard"])
        for rel in untracked:
            if Path(rel).suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            path = root / rel
            if not path.is_file():
                continue
            line_count = max(
                1, len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            )
            ranges.setdefault(rel.replace("\\", "/"), []).append((1, line_count))
    return {path: _coalesce(spans) for path, spans in ranges.items()}


def changed_symbols(
    root: Path,
    base: str = "main",
    *,
    mode: DiffMode = "local",
    facts_by_path: dict[str, ModuleFacts] | None = None,
) -> list[ChangedSymbol]:
    """Definitions that overlap changed line ranges in source files."""
    root = root.resolve()
    ranges = changed_line_ranges(root, base, mode=mode)
    found: list[ChangedSymbol] = []
    for rel, spans in sorted(ranges.items()):
        if Path(rel).suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        facts = (facts_by_path or {}).get(rel)
        if facts is None:
            path = root / rel
            if not path.is_file():
                continue
            facts = parse_module(path)
        found.extend(_symbols_for_file(rel, facts.definitions, spans))
    return found


def touches_only_non_symbols(root: Path, base: str = "main", *, mode: DiffMode = "local") -> bool:
    """True when source files changed but no def/import line was touched.

    Used for comments/formatting-only pass-through. Returns False when no
    source files changed (caller should handle that separately).
    """
    ranges = {
        p: s
        for p, s in changed_line_ranges(root, base, mode=mode).items()
        if Path(p).suffix.lower() in SOURCE_EXTENSIONS
    }
    if not ranges:
        return False
    for rel, spans in ranges.items():
        path = root / rel
        if not path.is_file():
            continue
        facts = parse_module(path)
        interesting_lines = {d.line for d in facts.definitions} | {i.line for i in facts.imports}
        if any(_line_in_spans(line, spans) for line in interesting_lines):
            return False
        text_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for start, end in spans:
            for line_no in range(start, end + 1):
                if line_no > len(text_lines):
                    continue
                stripped = text_lines[line_no - 1].strip()
                if stripped and not _is_comment_or_blank(stripped):
                    return False
    return True


def _is_comment_or_blank(stripped: str) -> bool:
    if not stripped:
        return True
    return (
        stripped.startswith("#")
        or stripped.startswith("//")
        or stripped.startswith("/*")
        or stripped.startswith("*")
    )


def _symbols_for_file(
    rel: str,
    definitions: list[Definition],
    spans: list[tuple[int, int]],
) -> list[ChangedSymbol]:
    if not definitions:
        return []
    ordered = sorted(definitions, key=lambda d: d.line)
    out: list[ChangedSymbol] = []
    for index, definition in enumerate(ordered):
        end = ordered[index + 1].line - 1 if index + 1 < len(ordered) else 10**9
        if any(start <= end and stop >= definition.line for start, stop in spans):
            # Span overlaps [definition.line, end]
            if any(max(start, definition.line) <= min(stop, end) for start, stop in spans):
                out.append(
                    ChangedSymbol(
                        path=rel,
                        name=definition.name,
                        kind=definition.kind,
                        line=definition.line,
                    )
                )
    return out


def _parse_diff(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    ranges: dict[str, list[tuple[int, int]]] = {}
    current: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            raw = line[4:].strip()
            if raw == "/dev/null":
                current = None
                continue
            if raw.startswith("b/"):
                raw = raw[2:]
            current = raw.replace("\\", "/")
            ranges.setdefault(current, [])
            continue
        if current is None:
            continue
        match = _HUNK_RE.match(line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        if count == 0:
            continue
        ranges[current].append((start, start + count - 1))
    return ranges


def _merge_ranges(
    into: dict[str, list[tuple[int, int]]],
    extra: dict[str, list[tuple[int, int]]],
) -> None:
    for path, spans in extra.items():
        into.setdefault(path, []).extend(spans)


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


def _line_in_spans(line: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= line <= end for start, end in spans)


def _git_diff(root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        # git diff returns 1 when differences exist with some options; accept 0.
        # With plain diff, returncode is 0 even when there are changes.
        raise GitDiffError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _git_lines(root: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitDiffError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
