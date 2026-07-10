"""File discovery for Focus Scan.

Ignore rules are delegated to git itself: `git ls-files` already knows
every .gitignore semantic (nested files, negations, global excludes),
so Focus never reimplements them. Outside a git repo, every Python file
is included.
"""

import subprocess
from pathlib import Path


def discover_python_files(root: Path) -> list[Path]:
    """Return sorted absolute paths of Python files under `root`.

    Inside a git repo: tracked and untracked files, minus anything
    .gitignore excludes. Outside a git repo: all `*.py` files.
    """
    root = root.resolve()
    listed = _git_listed_files(root)
    if listed is None:
        return sorted(p for p in root.rglob("*.py") if p.is_file())
    return sorted(
        path for name in listed if (path := root / name).suffix == ".py" and path.is_file()
    )


def _git_listed_files(root: Path) -> list[str] | None:
    """File paths relative to `root` per git, or None outside a git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()
