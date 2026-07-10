"""Parse cache: content-hash keyed ModuleFacts under .focus-cache/."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from focus.cli import app
from focus.scan.cache import (
    CACHE_SCHEMA_VERSION,
    cache_dir_for,
    cache_path,
    content_hash,
    parse_module_cached,
)
from focus.scan.parser import parse_source

runner = CliRunner()


def test_content_hash_stable():
    assert content_hash(b"abc") == content_hash(b"abc")
    assert content_hash(b"abc") != content_hash(b"abd")


def test_second_parse_hits_cache(tmp_path: Path):
    src = tmp_path / "mod.py"
    src.write_text("def hello():\n    return 1\n", encoding="utf-8")
    cache_dir = cache_dir_for(tmp_path)

    first = parse_module_cached(src, cache_dir=cache_dir, use_cache=True)
    entry = cache_path(cache_dir, content_hash(src.read_bytes()))
    assert entry.is_file()
    assert first.definitions[0].name == "hello"

    with patch("focus.scan.cache.parse_source") as mock_parse:
        second = parse_module_cached(src, cache_dir=cache_dir, use_cache=True)
        mock_parse.assert_not_called()

    assert second.definitions[0].name == "hello"
    assert second.path == src
    assert second.model_dump(exclude={"path"}) == first.model_dump(exclude={"path"})


def test_content_change_misses_cache(tmp_path: Path):
    src = tmp_path / "mod.py"
    src.write_text("def hello():\n    return 1\n", encoding="utf-8")
    cache_dir = cache_dir_for(tmp_path)
    parse_module_cached(src, cache_dir=cache_dir, use_cache=True)

    src.write_text("def goodbye():\n    return 2\n", encoding="utf-8")
    facts = parse_module_cached(src, cache_dir=cache_dir, use_cache=True)
    assert [d.name for d in facts.definitions] == ["goodbye"]


def test_no_cache_skips_read_and_write(tmp_path: Path):
    src = tmp_path / "mod.py"
    src.write_text("def hello():\n    return 1\n", encoding="utf-8")
    cache_dir = cache_dir_for(tmp_path)

    facts = parse_module_cached(src, cache_dir=cache_dir, use_cache=False)
    assert facts.definitions[0].name == "hello"
    assert not (cache_dir / CACHE_SCHEMA_VERSION).exists()


def test_scan_no_cache_cli(tmp_path: Path, glass_box_path: Path):
    # Copy one file into tmp so we control the cache root
    src = tmp_path / "auth_utils.py"
    src.write_text((glass_box_path / "auth_utils.py").read_text(encoding="utf-8"), encoding="utf-8")
    result = runner.invoke(app, ["scan", str(tmp_path), "--no-cache"])
    assert result.exit_code == 0
    assert "auth_utils.py" in result.output
    assert not (tmp_path / ".focus-cache").exists()


def test_scan_writes_cache(tmp_path: Path):
    src = tmp_path / "solo.py"
    src.write_text("import os\n", encoding="utf-8")
    result = runner.invoke(app, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    digest = content_hash(src.read_bytes())
    assert cache_path(cache_dir_for(tmp_path), digest).is_file()


def test_cached_facts_match_fresh_parse(glass_box_path: Path, tmp_path: Path):
    src = glass_box_path / "billing" / "service.py"
    cache_dir = cache_dir_for(tmp_path)
    cached = parse_module_cached(src, cache_dir=cache_dir, use_cache=True)
    fresh = parse_source(src.read_bytes(), src)
    assert cached.model_dump(exclude={"path"}) == fresh.model_dump(exclude={"path"})
