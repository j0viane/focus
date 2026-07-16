"""Assemble a Focus HUD for a local audit (diff seeds → blast radius)."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from focus.config import load_config
from focus.graph import build_graph, downstream_rings
from focus.hud.classify import (
    DEFAULT_CAVEAT,
    classify_impacts,
    is_danger_path,
    is_danger_zone,
    score_risk,
    shared_hub_reason,
)
from focus.hud.explain import ExplainContext, enrich_changed_symbols
from focus.hud.mermaid import render_mermaid, validate_mermaid_edges
from focus.ingest import changed_files, changed_source_files
from focus.ingest.diff import DiffMode
from focus.ingest.symbols import changed_line_ranges, changed_symbols, touches_only_non_symbols
from focus.llm.settings import resolve_llm_captions
from focus.models import (
    ChangedSymbolInfo,
    FocusHUD,
    ImpactNode,
    LineExplanation,
    ModuleFacts,
    RiskTier,
)
from focus.scan import cache_dir_for, discover_source_files, parse_module_cached
from focus.triggers import should_emit_diagram


def audit_local(
    root: Path,
    base: str = "main",
    *,
    use_cache: bool = True,
    overlays: dict[str, str] | None = None,
    llm_captions: bool | None = None,
) -> FocusHUD:
    """Build a HUD for working-tree changes vs `base`."""
    return run_audit(
        root,
        base=base,
        mode="local",
        use_cache=use_cache,
        overlays=overlays,
        llm_captions=llm_captions,
    )


def audit_pr(
    root: Path,
    base: str = "main",
    *,
    use_cache: bool = True,
    llm_captions: bool | None = None,
) -> FocusHUD:
    """Build a HUD for commits on this branch vs `base` (``base...HEAD``)."""
    return run_audit(
        root, base=base, mode="range", use_cache=use_cache, llm_captions=llm_captions
    )


def build_explain_context(
    root: Path,
    base: str = "main",
    *,
    mode: DiffMode = "local",
    use_cache: bool = True,
) -> ExplainContext | None:
    """Graph + facts for ``focus explain`` (no HUD render)."""
    root = root.resolve()
    config = load_config(root)
    fan_out = config.fan_out_threshold
    all_changed = changed_files(root, base, mode=mode)
    py_changed = changed_source_files(root, base, mode=mode)

    if not all_changed or not py_changed or touches_only_non_symbols(root, base, mode=mode):
        return None

    graph, facts_by_rel = _build_graph_index(
        root,
        use_cache=use_cache,
        cache_dir=cache_dir_for(root) if use_cache else None,
    )
    seeds = [path for path in py_changed if path in graph]
    symbols = changed_symbols(root, base, mode=mode, facts_by_path=facts_by_rel)
    symbol_infos = [
        ChangedSymbolInfo(
            path=s.path,
            name=s.name,
            kind=s.kind,  # type: ignore[arg-type]
            line=s.line,
            changed_lines=s.changed_lines,
        )
        for s in symbols
    ]
    if not symbol_infos:
        return None

    if not seeds:
        return ExplainContext(
            symbols=symbol_infos,
            graph=graph,
            seeds=[],
            danger_paths=set(),
            downstream_count=0,
            risk="LOW",
            facts_by_path=facts_by_rel,
        )

    rings = _merge_rings(graph, seeds)
    seed_set = set(seeds)
    rings = [(hops, [p for p in paths if p not in seed_set]) for hops, paths in rings]
    rings = [(hops, paths) for hops, paths in rings if paths]
    downstream_file_count = sum(len(paths) for _, paths in rings)

    if not should_emit_diagram(
        changed_paths=all_changed,
        python_seeds=seeds,
        has_downstream=bool(rings),
        downstream_file_count=downstream_file_count,
        graph=graph,
        fan_out_threshold=fan_out,
    ):
        return ExplainContext(
            symbols=symbol_infos,
            graph=graph,
            seeds=seeds,
            danger_paths=set(),
            downstream_count=0,
            risk="LOW",
            facts_by_path=facts_by_rel,
        )

    danger, _downstream = classify_impacts(
        rings,
        graph,
        fan_out_threshold=fan_out,
        seeds=seeds,
    )
    for seed in seeds:
        if is_danger_zone(seed, graph, fan_out_threshold=fan_out):
            danger.insert(0, ImpactNode(path=seed, hops=0, reason=""))

    total = sum(len(paths) for _, paths in rings)
    max_hops = max((hops for hops, _ in rings), default=0)
    risk = score_risk(
        downstream_count=max(total, 1 if danger else 0),
        max_hops=max(max_hops, 1 if danger else 0),
        danger_count=len(danger),
    )
    return ExplainContext(
        symbols=symbol_infos,
        graph=graph,
        seeds=seeds,
        danger_paths={n.path for n in danger},
        downstream_count=total,
        risk=risk,
        facts_by_path=facts_by_rel,
    )


def run_audit(
    root: Path,
    base: str = "main",
    *,
    mode: DiffMode = "local",
    use_cache: bool = True,
    overlays: dict[str, str] | None = None,
    llm_captions: bool | None = None,
) -> FocusHUD:
    """Build a HUD for changes vs `base` in local or PR-range mode."""
    root = root.resolve()
    config = load_config(root)
    fan_out = config.fan_out_threshold
    overlays = overlays or {}
    use_llm = resolve_llm_captions(
        force=llm_captions,
        overlays=overlays or None,
        config=config,
    )
    all_changed = changed_files(root, base, mode=mode)
    py_changed = changed_source_files(root, base, mode=mode)
    line_ranges = changed_line_ranges(root, base, mode=mode)

    # Graph from disk first; overlays replace facts/ranges for dirty buffers.
    cache_dir = cache_dir_for(root) if use_cache else None
    graph, facts_by_rel = _build_graph_index(root, use_cache=use_cache, cache_dir=cache_dir)

    if overlays and mode == "local":
        from focus.ingest.overlay import apply_overlays

        all_changed, py_changed, line_ranges, facts_by_rel = apply_overlays(
            root,
            base,
            overlays=overlays,
            changed_paths=all_changed,
            source_paths=py_changed,
            line_ranges=line_ranges,
            facts_by_path=facts_by_rel,
        )

    if not all_changed:
        return FocusHUD(
            mode="pass_through",
            seed="(none)",
            summary=(f"**Focus:** No changes vs `{base}` — nothing to audit. **LOW** risk."),
            risk_tier="LOW",
        )

    if not py_changed:
        sample = ", ".join(f"`{p}`" for p in all_changed[:5])
        more = "" if len(all_changed) <= 5 else f" (+{len(all_changed) - 5} more)"
        return FocusHUD(
            mode="pass_through",
            seed="(non-source)",
            summary=(
                f"**Focus:** Changed non-source paths only ({sample}{more}) — "
                f"no executable dependency graph for this diff. **LOW** risk."
            ),
            risk_tier="LOW",
        )

    # Unsaved overlays may be blank-only inside a def — still want edit-shaped captions.
    if not overlays and touches_only_non_symbols(root, base, mode=mode):
        label = ", ".join(f"`{p}`" for p in py_changed[:5])
        return FocusHUD(
            mode="pass_through",
            seed=", ".join(py_changed),
            summary=(
                f"**Focus:** {label} changed, but only comments/blank lines — "
                f"no definitions or imports touched. **LOW** risk."
            ),
            risk_tier="LOW",
        )

    seeds = [path for path in py_changed if path in graph]
    missing = [path for path in py_changed if path not in graph]
    # Overlay files may be new to the graph index path set — keep them as seeds if present.
    for rel in overlays:
        if rel in py_changed and rel not in seeds and rel in graph:
            seeds.append(rel)
    symbols = changed_symbols(
        root,
        base,
        mode=mode,
        facts_by_path=facts_by_rel,
        line_ranges=line_ranges,
    )
    symbol_infos = [
        ChangedSymbolInfo(
            path=s.path,
            name=s.name,
            kind=s.kind,  # type: ignore[arg-type]
            line=s.line,
            changed_lines=s.changed_lines,
        )
        for s in symbols
    ]

    if not seeds:
        detail = ", ".join(f"`{p}`" for p in py_changed[:5])
        return _with_line_explanations(
            FocusHUD(
            mode="pass_through",
            seed="(unscanned)",
            summary=(
                f"**Focus:** Source changes ({detail}) were not in the scanned "
                f"graph (deleted or ignored). **LOW** risk."
            ),
            risk_tier="LOW",
            changed_symbols=_enrich_symbols(
                symbol_infos,
                graph,
                seeds=[],
                facts_by_path=facts_by_rel,
                overlay_texts=overlays,
                llm_captions=use_llm,
            ),
            caveat=DEFAULT_CAVEAT if missing else None,
        ),
            line_ranges,
            facts_by_path=facts_by_rel,
            overlay_texts=overlays,
        )

    rings = _merge_rings(graph, seeds)
    seed_set = set(seeds)
    rings = [(hops, [p for p in paths if p not in seed_set]) for hops, paths in rings]
    rings = [(hops, paths) for hops, paths in rings if paths]

    has_downstream = bool(rings)
    downstream_file_count = sum(len(paths) for _, paths in rings)
    if not should_emit_diagram(
        changed_paths=all_changed,
        python_seeds=seeds,
        has_downstream=has_downstream,
        downstream_file_count=downstream_file_count,
        graph=graph,
        fan_out_threshold=fan_out,
    ):
        label = ", ".join(f"`{s}`" for s in seeds)
        return _with_line_explanations(
            FocusHUD(
            mode="pass_through",
            seed=", ".join(seeds),
            summary=(
                f"**Focus:** Changed {label} — no downstream dependents and "
                f"no Danger Zone seed. **LOW** risk."
            ),
            risk_tier="LOW",
            isolated=seeds,
            changed_symbols=_enrich_symbols(
                symbol_infos,
                graph,
                seeds=seeds,
                facts_by_path=facts_by_rel,
                overlay_texts=overlays,
                llm_captions=use_llm,
            ),
        ),
            line_ranges,
            facts_by_path=facts_by_rel,
            overlay_texts=overlays,
        )

    return _with_line_explanations(
        _full_audit_hud(
        graph,
        seeds,
        rings,
        symbol_infos,
        fan_out_threshold=fan_out,
        facts_by_path=facts_by_rel,
        overlay_texts=overlays,
        llm_captions=use_llm,
    ),
        line_ranges,
        facts_by_path=facts_by_rel,
        overlay_texts=overlays,
    )


def _full_audit_hud(
    graph: nx.DiGraph,
    seeds: list[str],
    rings: list[tuple[int, list[str]]],
    symbol_infos: list[ChangedSymbolInfo],
    *,
    fan_out_threshold: int,
    facts_by_path: dict[str, ModuleFacts],
    overlay_texts: dict[str, str] | None = None,
    llm_captions: bool = False,
) -> FocusHUD:
    danger, downstream = classify_impacts(
        rings,
        graph,
        fan_out_threshold=fan_out_threshold,
        seeds=seeds,
    )
    for seed in seeds:
        if is_danger_zone(seed, graph, fan_out_threshold=fan_out_threshold):
            if is_danger_path(seed):
                reason = "You changed an API, schema, or config file."
            else:
                reason = shared_hub_reason(graph, seed, changed=True)
            danger.insert(
                0,
                ImpactNode(
                    path=seed,
                    hops=0,
                    reason=reason,
                ),
            )

    total = sum(len(paths) for _, paths in rings)
    max_hops = max((hops for hops, _ in rings), default=0)
    risk = score_risk(
        downstream_count=max(total, 1 if danger else 0),
        max_hops=max(max_hops, 1 if danger else 0),
        danger_count=len(danger),
    )
    danger_paths = {n.path for n in danger}
    isolated = [s for s in seeds if s not in danger_paths and total == 0]
    symbol_infos = enrich_changed_symbols(
        symbol_infos,
        graph=graph,
        seeds=seeds,
        danger_paths=danger_paths,
        downstream_count=total,
        risk=risk,
        facts_by_path=facts_by_path,
        overlay_texts=overlay_texts,
        llm_captions=llm_captions,
    )

    mermaid = render_mermaid(graph, seeds, rings)
    invalid = validate_mermaid_edges(graph, mermaid)
    if invalid:
        raise ValueError(f"Mermaid edges not in graph: {invalid}")

    seed_label = ", ".join(f"`{s}`" for s in seeds)
    file_word = "file" if total == 1 else "files"
    hop_bit = f", up to {max_hops} {'hop' if max_hops == 1 else 'hops'} away" if max_hops else ""
    danger_bit = ""
    if danger:
        names = ", ".join(f"`{n.path}`" for n in danger[:3])
        danger_bit = f" Danger Zones: {names}."
    symbol_bit = ""
    if symbol_infos:
        shown = ", ".join(f"`{s.name}`" for s in symbol_infos[:4])
        extra = "" if len(symbol_infos) <= 4 else f" (+{len(symbol_infos) - 4} more)"
        symbol_bit = f" Touched symbols: {shown}{extra}."

    return FocusHUD(
        mode="full",
        seed=", ".join(seeds),
        summary=(
            f"Audited local changes to {seed_label}. **{risk}** risk — "
            f"{total} downstream {file_word}{hop_bit}.{danger_bit}{symbol_bit}"
        ),
        risk_tier=risk,
        mermaid=mermaid,
        danger_zones=danger,
        downstream=downstream,
        isolated=isolated,
        changed_symbols=symbol_infos,
        caveat=DEFAULT_CAVEAT,
    )


def _merge_rings(
    graph: nx.DiGraph,
    seeds: list[str],
) -> list[tuple[int, list[str]]]:
    best: dict[str, int] = {}
    for seed in seeds:
        for hops, paths in downstream_rings(graph, seed):
            for path in paths:
                if path not in best or hops < best[path]:
                    best[path] = hops
    rings: dict[int, list[str]] = {}
    for path, hops in best.items():
        rings.setdefault(hops, []).append(path)
    return [(hops, sorted(paths)) for hops, paths in sorted(rings.items())]


def _contiguous_line_runs(lines: list[int]) -> list[list[int]]:
    if not lines:
        return []
    ordered = sorted(set(lines))
    runs: list[list[int]] = [[ordered[0]]]
    for line in ordered[1:]:
        if line == runs[-1][-1] + 1:
            runs[-1].append(line)
        else:
            runs.append([line])
    return runs


def orphan_line_explanations(
    symbols: list[ChangedSymbolInfo],
    ranges: dict[str, list[tuple[int, int]]],
    facts_by_path: dict[str, ModuleFacts] | None = None,
    overlay_texts: dict[str, str] | None = None,
) -> list[LineExplanation]:
    """Diff hunks not covered by any changed symbol's ``changed_lines``."""
    from pathlib import Path as _Path

    from focus.hud.explain import caption_for_orphan_edit
    from focus.scan.walker import SOURCE_EXTENSIONS

    covered: dict[str, set[int]] = {}
    for symbol in symbols:
        covered.setdefault(symbol.path, set()).update(symbol.changed_lines)

    facts_by_path = facts_by_path or {}
    overlay_texts = overlay_texts or {}
    out: list[LineExplanation] = []
    for path, spans in ranges.items():
        if _Path(path).suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        orphan_lines: list[int] = []
        symbol_lines = covered.get(path, set())
        for start, end in spans:
            for line in range(start, end + 1):
                if line not in symbol_lines:
                    orphan_lines.append(line)
        facts = facts_by_path.get(path)
        source: list[str] | None = None
        if path in overlay_texts:
            source = overlay_texts[path].splitlines()
        elif facts is not None and facts.path.is_file():
            try:
                source = facts.path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                source = None
        for run in _contiguous_line_runs(orphan_lines):
            if source is not None:
                run_text = [source[line - 1] for line in run if 0 < line <= len(source)]
            else:
                run_text = []
            out.append(
                LineExplanation(
                    path=path,
                    line=run[0],
                    changed_lines=run,
                    detail=caption_for_orphan_edit(
                        run_text,
                        facts=facts,
                        hunk_lines=run,
                    ),
                )
            )
    return out


def _with_line_explanations(
    hud: FocusHUD,
    ranges: dict[str, list[tuple[int, int]]],
    facts_by_path: dict[str, ModuleFacts] | None = None,
    overlay_texts: dict[str, str] | None = None,
) -> FocusHUD:
    orphans = orphan_line_explanations(
        hud.changed_symbols,
        ranges,
        facts_by_path=facts_by_path,
        overlay_texts=overlay_texts,
    )
    if not orphans:
        return hud
    return hud.model_copy(update={"line_explanations": orphans})


def _enrich_symbols(
    symbol_infos: list[ChangedSymbolInfo],
    graph: nx.DiGraph,
    *,
    seeds: list[str],
    danger_paths: set[str] | None = None,
    downstream_count: int = 0,
    risk: RiskTier = "LOW",
    facts_by_path: dict[str, ModuleFacts] | None = None,
    overlay_texts: dict[str, str] | None = None,
    llm_captions: bool = False,
) -> list[ChangedSymbolInfo]:
    if not symbol_infos:
        return []
    return enrich_changed_symbols(
        symbol_infos,
        graph=graph,
        seeds=seeds,
        danger_paths=danger_paths or set(),
        downstream_count=downstream_count,
        risk=risk,
        facts_by_path=facts_by_path,
        overlay_texts=overlay_texts,
        llm_captions=llm_captions,
    )


def _build_graph_index(
    root: Path,
    *,
    use_cache: bool,
    cache_dir: Path | None = None,
) -> tuple[nx.DiGraph, dict[str, ModuleFacts]]:
    if cache_dir is None and use_cache:
        cache_dir = cache_dir_for(root)
    facts_list = [
        parse_module_cached(path, cache_dir=cache_dir, use_cache=use_cache)
        for path in discover_source_files(root)
    ]
    facts_by_rel = {
        facts.path.resolve().relative_to(root).as_posix(): facts for facts in facts_list
    }
    graph = build_graph(facts_list, root)
    return graph, facts_by_rel
