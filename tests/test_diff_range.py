"""PR-range (base...HEAD) diff mode for CI audits."""

import shutil
import subprocess
from pathlib import Path

from focus.ingest import changed_python_files


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_range_mode_sees_committed_change_not_untracked(tmp_path: Path, glass_box_path: Path):
    repo = tmp_path / "repo"
    shutil.copytree(glass_box_path, repo)
    _git(repo, "init")
    _git(repo, "config", "user.email", "focus@test")
    _git(repo, "config", "user.name", "Focus Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    _git(repo, "branch", "-M", "main")
    _git(repo, "checkout", "-b", "feature")

    (repo / "auth_utils.py").write_text(
        (repo / "auth_utils.py")
        .read_text()
        .replace(
            "return token == FIXTURE_SECRET",
            "return token == FIXTURE_SECRET  # x",
        )
    )
    _git(repo, "add", "auth_utils.py")
    _git(repo, "commit", "-m", "auth change")
    (repo / "orphan.py").write_text("x = 1\n")  # untracked — local only

    ranged = changed_python_files(repo, "main", mode="range")
    local = changed_python_files(repo, "main", mode="local")
    assert "auth_utils.py" in ranged
    assert "orphan.py" not in ranged
    assert "orphan.py" in local
