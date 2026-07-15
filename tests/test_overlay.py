"""Unsaved buffer overlays for live IDE audits."""

from pathlib import Path

from focus.ingest.overlay import apply_overlays, line_ranges_from_texts, load_overlay_file
from focus.models import ModuleFacts
from focus.scan.parser import parse_source


def test_line_ranges_from_texts_counts_inserted_blanks():
    base = "def helper():\n    x = 1\n    return x\n"
    overlay = "def helper():\n    x = 1\n\n\n\n    return x\n"
    spans = line_ranges_from_texts(base, overlay)
    assert spans == [(3, 5)]


def test_load_overlay_file(tmp_path: Path):
    path = tmp_path / "overlay.json"
    path.write_text('{"src/foo.py": "print(1)\\n"}', encoding="utf-8")
    assert load_overlay_file(path) == {"src/foo.py": "print(1)\n"}


def test_apply_overlays_replaces_ranges_and_facts(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "mod.py"
    target.write_text("def helper():\n    return 1\n", encoding="utf-8")

    # No git base → empty base text; overlay still wins for ranges + facts.
    overlays = {"mod.py": "def helper():\n\n\n    return 1\n"}
    changed, sources, ranges, facts = apply_overlays(
        repo,
        "main",
        overlays=overlays,
        changed_paths=[],
        source_paths=[],
        line_ranges={},
        facts_by_path={},
    )
    assert "mod.py" in changed
    assert "mod.py" in sources
    assert ranges["mod.py"]
    assert isinstance(facts["mod.py"], ModuleFacts)
    assert any(d.name == "helper" for d in facts["mod.py"].definitions)


def test_audit_local_overlay_blank_caption(tmp_path: Path):
    """Overlay-only blanks produce Added N blank lines without writing disk."""
    import networkx as nx

    from focus.hud.explain import enrich_changed_symbols
    from focus.models import ChangedSymbolInfo

    path = tmp_path / "blankish.py"
    disk = "def helper():\n    x = 1\n    return x\n"
    path.write_text(disk, encoding="utf-8")
    buffer = "def helper():\n    x = 1\n\n\n\n    return x\n"
    facts = parse_source(buffer.encode("utf-8"), path)
    enriched = enrich_changed_symbols(
        [
            ChangedSymbolInfo(
                path="blankish.py",
                name="helper",
                kind="function",
                line=1,
                changed_lines=[3, 4, 5],
            )
        ],
        graph=nx.DiGraph(),
        seeds=["blankish.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={"blankish.py": facts},
        overlay_texts={"blankish.py": buffer},
    )[0]
    assert enriched.hunk_details
    assert enriched.hunk_details[0].detail == "Added 3 blank lines."
    assert path.read_text(encoding="utf-8") == disk