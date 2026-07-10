"""Git diff ingest — which files changed vs a base ref.

Two modes:
- ``local`` — working tree + index + untracked vs base (author pre-flight)
- ``range`` — commits on this branch vs base (``base...HEAD``, PR / CI)

Focus still builds the full-repo graph; the diff only answers "what changed."
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

DiffMode = Literal["local", "range"]


from focus.scan.walker import SOURCE_EXTENSIONS


class GitDiffError(RuntimeError):
    """Raised when git is missing, the path is not a repo, or the base ref is unknown."""


def changed_files(root: Path, base: str = "main", *, mode: DiffMode = "local") -> list[str]:
    """Return sorted posix paths changed vs `base` for the given mode."""
    root = root.resolve()
    _require_git_repo(root)
    resolved_base = resolve_base_ref(root, base)

    if mode == "range":
        return sorted(
            _git_lines(
                root,
                ["diff", "--name-only", "--diff-filter=ACMR", f"{resolved_base}...HEAD"],
            )
        )

    names: set[str] = set()
    names.update(_git_lines(root, ["diff", "--name-only", "--diff-filter=ACMR", resolved_base]))
    names.update(
        _git_lines(root, ["diff", "--name-only", "--cached", "--diff-filter=ACMR", resolved_base])
    )
    names.update(_git_lines(root, ["ls-files", "--others", "--exclude-standard"]))
    return sorted(names)


def changed_python_files(root: Path, base: str = "main", *, mode: DiffMode = "local") -> list[str]:
    """Subset of `changed_files` that end in `.py`."""
    return [path for path in changed_files(root, base, mode=mode) if path.endswith(".py")]


def changed_source_files(root: Path, base: str = "main", *, mode: DiffMode = "local") -> list[str]:
    """Subset of `changed_files` Focus can parse (Python + JS/TS)."""
    return [
        path
        for path in changed_files(root, base, mode=mode)
        if Path(path).suffix.lower() in SOURCE_EXTENSIONS
    ]


def resolve_base_ref(root: Path, preferred: str = "main") -> str:
    """Resolve a usable base ref: preferred SHA/branch, then main, then master."""
    candidates = [preferred]
    for name in ("main", "master"):
        if name not in candidates:
            candidates.append(name)
    for candidate in candidates:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", f"{candidate}^{{commit}}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return candidate
    raise GitDiffError(
        f"Could not find base ref among {candidates}. "
        f"Pass --base with a branch or commit that exists in {root}."
    )


def _require_git_repo(root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise GitDiffError("git is not installed or not on PATH.") from exc
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise GitDiffError(f"{root} is not a git repository.")


def _git_lines(root: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitDiffError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
