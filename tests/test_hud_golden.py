"""HUD golden / structural tests — assert contract shape, not brittle prose."""

from pathlib import Path

from focus.graph import build_graph, downstream_rings
from focus.hud import build_hud, render_hud
from focus.hud.classify import is_danger_zone, score_risk
from focus.hud.mermaid import validate_mermaid_edges
from focus.hud.render import MAX_PR_BLAST_BULLETS, MAX_PR_SYMBOLS
from focus.models import ChangedSymbolInfo, FocusHUD, ImpactNode
from focus.scan import discover_python_files, parse_module


def _hud_for(glass_box_path: Path, relative: str):
    facts = [parse_module(f) for f in discover_python_files(glass_box_path)]
    graph = build_graph(facts, glass_box_path)
    rings = downstream_rings(graph, relative)
    return graph, build_hud(graph, relative, rings)


def test_auth_utils_full_hud(glass_box_path: Path):
    graph, hud = _hud_for(glass_box_path, "auth_utils.py")
    assert hud.mode == "full"
    assert hud.risk_tier in {"HIGH", "CRITICAL"}
    assert hud.mermaid is not None
    assert "```mermaid" in render_hud(hud)
    assert validate_mermaid_edges(graph, hud.mermaid) == []

    danger_paths = {n.path for n in hud.danger_zones}
    assert "api/routes.py" in danger_paths

    down_paths = {n.path for n in hud.downstream}
    assert "billing/service.py" in down_paths
    assert "dashboard/views.py" in down_paths
    assert "jobs/worker.py" in down_paths
    assert hud.caveat is not None


def test_auth_utils_is_high_fan_out_danger(glass_box_path: Path):
    facts = [parse_module(f) for f in discover_python_files(glass_box_path)]
    graph = build_graph(facts, glass_box_path)
    assert is_danger_zone("auth_utils.py", graph) is True
    assert is_danger_zone("billing/service.py", graph) is False
    assert is_danger_zone("dashboard/views.py", graph) is False
    assert is_danger_zone("jobs/worker.py", graph) is False


def test_routes_pass_through(glass_box_path: Path):
    _, hud = _hud_for(glass_box_path, "api/routes.py")
    assert hud.mode == "pass_through"
    assert hud.risk_tier == "LOW"
    assert hud.mermaid is None
    assert "LOW" in render_hud(hud)
    assert "```mermaid" not in render_hud(hud)


def test_mermaid_contains_seed_and_legend(glass_box_path: Path):
    _, hud = _hud_for(glass_box_path, "auth_utils.py")
    assert "auth_utils.py" in (hud.mermaid or "")
    assert "change flows to" in (hud.mermaid or "")
    rendered = render_hud(hud)
    assert "each box is a **file**" in rendered


def test_danger_zone_path_heuristics():
    assert is_danger_zone("api/routes.py")
    assert is_danger_zone("app/models.py")
    assert not is_danger_zone("billing/service.py")


def test_risk_scoring_table():
    assert score_risk(downstream_count=0, max_hops=0, danger_count=0) == "LOW"
    assert score_risk(downstream_count=0, max_hops=0, danger_count=1) == "HIGH"
    assert score_risk(downstream_count=1, max_hops=1, danger_count=0) == "MEDIUM"
    assert score_risk(downstream_count=3, max_hops=1, danger_count=0) == "HIGH"
    assert score_risk(downstream_count=3, max_hops=2, danger_count=1) == "CRITICAL"


def test_render_hud_caps_your_changes_and_blast_lists():
    """PR / CLI markdown stays scannable — ROA caps on Your changes + blast lists."""
    symbols = [
        ChangedSymbolInfo(
            path="helpers.py",
            name=f"_helper_{i}",
            kind="function",
            line=i + 1,
            explanation="x" * 200,
            detail="short detail" if i == 0 else "",
            summary="short summary" if i == 1 else "",
        )
        for i in range(12)
    ]
    symbols.extend(
        [
            ChangedSymbolInfo(
                path="api/routes.py",
                name="public_handler",
                kind="function",
                line=1,
                detail="prefer this over explanation",
                explanation="long explanation that should not appear when detail exists",
            ),
            ChangedSymbolInfo(
                path="util.py",
                name="public_util",
                kind="function",
                line=2,
                explanation="only explanation",
            ),
            *[
                ChangedSymbolInfo(
                    path=f"more_{i}.py",
                    name=f"sym_{i}",
                    kind="function",
                    line=1,
                    explanation=f"extra {i}",
                )
                for i in range(6)
            ],
        ]
    )
    assert len(symbols) == 20

    danger = [ImpactNode(path="api/routes.py", hops=0, reason="shared route")]
    downstream = [
        ImpactNode(path=f"down_{i}.py", hops=1, reason=f"imports seed ({i})")
        for i in range(12)
    ]
    isolated = [f"alone_{i}.py" for i in range(12)]

    hud = FocusHUD(
        mode="full",
        seed="helpers.py",
        summary="Touched many symbols. **HIGH** risk.",
        risk_tier="HIGH",
        mermaid="flowchart LR\n  A --> B",
        danger_zones=danger,
        downstream=downstream,
        isolated=isolated,
        changed_symbols=symbols,
    )
    rendered = render_hud(hud)
    your_section = rendered.split("### Architecture impact")[0]
    symbol_bullets = [
        line
        for line in your_section.splitlines()
        if line.startswith("- `") and "→" in line
    ]
    assert len(symbol_bullets) == MAX_PR_SYMBOLS
    assert "…and 12 more changed symbols" in rendered
    assert "focus audit --format json" in rendered
    assert "prefer this over explanation" in rendered
    assert "long explanation that should not appear" not in rendered
    # Danger Zones uncapped; Also affected / Not pulled in capped
    assert "`api/routes.py` — shared route" in rendered
    also = rendered.split("🟡 **Also affected**")[1].split("🟢 **Not pulled in**")[0]
    not_pulled = rendered.split("🟢 **Not pulled in**")[1]
    assert also.count("\n- `") == MAX_PR_BLAST_BULLETS
    assert "…and 4 more" in also
    assert not_pulled.count("\n- `") == MAX_PR_BLAST_BULLETS
    assert "…and 4 more" in not_pulled
    # Public / danger-zone symbols sort before private helpers
    first_bullet = next(line for line in your_section.splitlines() if line.startswith("- `"))
    assert "public_handler" in first_bullet or "public_util" in first_bullet
