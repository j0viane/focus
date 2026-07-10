"""Git diff ingest — which files changed vs a base ref.

This is the seed source for `focus audit --local`. Focus still builds the
full-repo graph; the diff only answers "what changed," never "what exists."
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitDiffError(RuntimeError):
    """Raised when git is missing, the path is not a repo, or the base ref is unknown."""


def changed_files(root: Path, base: str = "main") -> list[str]:
    """Return sorted posix paths changed vs `base` (working tree + index).

    Includes: modifications vs base, staged changes vs base, and untracked
    files (so new modules you have not committed yet still get audited).
    Deletes are omitted — a deleted path is not a graph seed.
    """
    root = root.resolve()
    _require_git_repo(root)
    resolved_base = resolve_base_ref(root, base)

    names: set[str] = set()
    names.update(_git_lines(root, ["diff", "--name-only", "--diff-filter=ACMR", resolved_base]))
    names.update(
        _git_lines(root, ["diff", "--name-only", "--cached", "--diff-filter=ACMR", resolved_base])
    )
    names.update(_git_lines(root, ["ls-files", "--others", "--exclude-standard"]))
    return sorted(names)


def changed_python_files(root: Path, base: str = "main") -> list[str]:
    """Subset of `changed_files` that end in `.py`."""
    return [path for path in changed_files(root, base) if path.endswith(".py")]


def resolve_base_ref(root: Path, preferred: str = "main") -> str:
    """Resolve a usable base ref: preferred, then main, then master."""
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
