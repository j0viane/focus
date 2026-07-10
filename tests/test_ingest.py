"""Git diff ingest tests — synthetic repos under tmp_path."""

import subprocess
from pathlib import Path

import pytest

from focus.ingest import GitDiffError, changed_files, changed_python_files, resolve_base_ref


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "focus@test")
    _git(root, "config", "user.name", "Focus Test")
    (root / "keep.py").write_text("x = 1\n")
    _git(root, "add", "keep.py")
    _git(root, "commit", "-m", "init")
    _git(root, "branch", "-M", "main")


def test_resolve_base_prefers_main(tmp_path: Path):
    _init_repo(tmp_path)
    assert resolve_base_ref(tmp_path, "main") == "main"


def test_changed_python_files_includes_unstaged_and_untracked(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / "keep.py").write_text("x = 2\n")
    (tmp_path / "new_mod.py").write_text("y = 1\n")
    (tmp_path / "README.md").write_text("docs\n")

    assert changed_python_files(tmp_path, "main") == ["keep.py", "new_mod.py"]
    assert "README.md" in changed_files(tmp_path, "main")


def test_changed_files_outside_git_raises(tmp_path: Path):
    with pytest.raises(GitDiffError):
        changed_files(tmp_path, "main")
