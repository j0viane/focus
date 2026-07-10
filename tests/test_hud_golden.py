"""HUD golden / structural tests — assert contract shape, not brittle prose."""

from pathlib import Path

from focus.graph import build_graph, downstream_rings
from focus.hud import build_hud, render_hud
from focus.hud.classify import is_danger_zone, score_risk
from focus.hud.mermaid import validate_mermaid_edges
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
