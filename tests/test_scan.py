"""File discovery tests: git-aware scanning against the glass_box fixture."""

import subprocess
from pathlib import Path

from focus.scan import discover_python_files


def relative_names(files: list[Path], root: Path) -> list[str]:
    return [f.relative_to(root.resolve()).as_posix() for f in files]


def test_discovers_all_fixture_files(glass_box_path: Path) -> None:
    files = discover_python_files(glass_box_path)
    assert relative_names(files, glass_box_path) == [
        "api/routes.py",
        "auth_utils.py",
        "billing/service.py",
        "dashboard/views.py",
    ]


def test_gitignored_files_are_excluded(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / "kept.py").write_text("x = 1\n")
    (tmp_path / "generated.py").write_text("y = 2\n")
    (tmp_path / ".gitignore").write_text("generated.py\n")

    files = discover_python_files(tmp_path)

    assert relative_names(files, tmp_path) == ["kept.py"]


def test_non_git_directory_falls_back_to_full_walk(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("a = 1\n")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "b.py").write_text("b = 2\n")
    (tmp_path / "notes.txt").write_text("not python\n")

    files = discover_python_files(tmp_path)

    assert relative_names(files, tmp_path) == ["a.py", "pkg/b.py"]
