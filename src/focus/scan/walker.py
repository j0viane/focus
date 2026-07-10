"""File discovery for Focus Scan.

Ignore rules are delegated to git itself: `git ls-files` already knows
every .gitignore semantic (nested files, negations, global excludes),
so Focus never reimplements them. Outside a git repo, every matching
source file is included.

When the scan root is a subdirectory of a git work tree, paths from
``git ls-files`` (repo-relative) are rewritten relative to that root so
nested packages still resolve.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from focus.scan.js_parser import SOURCE_EXTENSIONS as JS_SOURCE_EXTENSIONS

_PYTHON_EXTENSIONS = frozenset({".py"})
SOURCE_EXTENSIONS = _PYTHON_EXTENSIONS | JS_SOURCE_EXTENSIONS


def discover_python_files(root: Path) -> list[Path]:
    """Return sorted absolute paths of Python files under `root`."""
    return discover_source_files(root, extensions=_PYTHON_EXTENSIONS)


def discover_source_files(
    root: Path,
    *,
    extensions: frozenset[str] | None = None,
) -> list[Path]:
    """Return sorted absolute paths of source files under `root`.

    Inside a git repo: tracked and untracked files, minus anything
    .gitignore excludes. Outside a git repo: all matching extensions.
    Default extensions: Python + JS/TS.
    """
    root = root.resolve()
    exts = extensions if extensions is not None else SOURCE_EXTENSIONS
    listed = _git_listed_files(root)
    if listed is None:
        return sorted(
            p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts
        )
    return sorted(
        path
        for name in listed
        if (path := root / name).suffix.lower() in exts and path.is_file()
    )


def _git_listed_files(root: Path) -> list[str] | None:
    """File paths relative to `root` per git, or None outside a git repo."""
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if top.returncode != 0:
        return None
    toplevel = Path(top.stdout.strip()).resolve()

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(toplevel),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None

    rel_root = root.relative_to(toplevel).as_posix() if root != toplevel else ""
    out: list[str] = []
    for name in result.stdout.splitlines():
        if not name:
            continue
        if rel_root:
            prefix = rel_root + "/"
            if name == rel_root:
                continue
            if not name.startswith(prefix):
                continue
            name = name[len(prefix) :]
        out.append(name)
    return out
