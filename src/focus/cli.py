"""Typer entrypoint for the Focus CLI."""

from __future__ import annotations

import json
from enum import Enum
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

import typer

from focus.audit import audit_local, audit_pr, build_explain_context
from focus.graph import build_graph, downstream_rings
from focus.hud import build_hud, render_hud
from focus.hud.explain import ExplainContext, explain_symbols
from focus.hud.explain_render import render_explanations_json, render_explanations_markdown
from focus.ingest import GitDiffError
from focus.models import FocusHUD
from focus.scan import cache_dir_for, discover_source_files, parse_module_cached

app = typer.Typer(
    name="focus",
    help="Blast radius you can defend — evidence-only, before you merge.",
    no_args_is_help=True,
)


class OutputFormat(str, Enum):
    markdown = "markdown"
    json = "json"


@app.command()
def version() -> None:
    """Print the installed Focus version."""
    typer.echo(package_version("focus-hud"))


@app.command()
def scan(
    path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, help="Repository root to scan."),
    ] = Path("."),
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Bypass .focus-cache/ and re-parse every file."),
    ] = False,
) -> None:
    """Index the repo's source files: imports, definitions, calls per file."""
    files = discover_source_files(path)
    root = path.resolve()
    cache_dir = None if no_cache else cache_dir_for(root)
    total_imports = total_defs = total_calls = 0
    for file in files:
        facts = parse_module_cached(file, cache_dir=cache_dir, use_cache=not no_cache)
        total_imports += len(facts.imports)
        total_defs += len(facts.definitions)
        total_calls += len(facts.calls)
        typer.echo(
            f"{file.relative_to(root).as_posix()} — "
            f"{len(facts.imports)} imports · "
            f"{len(facts.definitions)} defs · "
            f"{len(facts.calls)} calls"
        )
    typer.echo(
        f"{len(files)} source file(s) indexed: "
        f"{total_imports} imports, {total_defs} definitions, {total_calls} calls"
    )


@app.command()
def trace(
    file: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, help="File to trace dependents of."),
    ],
    root: Annotated[
        Path,
        typer.Option(exists=True, file_okay=False, help="Repository root to scan."),
    ] = Path("."),
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write HUD output here (markdown or JSON)."),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="HUD output format (markdown or json)."),
    ] = OutputFormat.markdown,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Bypass .focus-cache/ and re-parse every file."),
    ] = False,
) -> None:
    """Show the Focus HUD for FILE: summary, Mermaid map, blast radius rings."""
    try:
        target = file.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        typer.echo(f"{file} is not inside the scan root {root.resolve()}")
        raise typer.Exit(1) from None

    cache_dir = None if no_cache else cache_dir_for(root)
    facts = [
        parse_module_cached(f, cache_dir=cache_dir, use_cache=not no_cache)
        for f in discover_source_files(root)
    ]
    graph = build_graph(facts, root)
    if target not in graph:
        typer.echo(f"{target} was not among the scanned source files under {root.resolve()}")
        raise typer.Exit(1)

    rings = downstream_rings(graph, target)
    hud = build_hud(graph, target, rings)
    _emit_hud(hud, out, output_format)


@app.command()
def audit(
    local: Annotated[
        bool,
        typer.Option("--local", help="Audit working tree + index vs a base branch."),
    ] = False,
    base: Annotated[
        str,
        typer.Option(help="Git base ref to diff against (default: main)."),
    ] = "main",
    path: Annotated[
        Path,
        typer.Option(exists=True, file_okay=False, help="Repository root to audit."),
    ] = Path("."),
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write HUD output here (markdown or JSON)."),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="HUD output format (markdown or json)."),
    ] = OutputFormat.markdown,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Bypass .focus-cache/ and re-parse every file."),
    ] = False,
    overlay_file: Annotated[
        Path | None,
        typer.Option(
            "--overlay-file",
            exists=True,
            dir_okay=False,
            help="JSON map of repo-relative paths → unsaved buffer text (IDE live overlay).",
        ),
    ] = None,
) -> None:
    """Pre-merge blast radius for local changes or a PR branch vs base."""
    overlays: dict[str, str] | None = None
    if overlay_file is not None:
        from focus.ingest.overlay import load_overlay_file

        try:
            overlays = load_overlay_file(overlay_file)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            typer.echo(f"Invalid --overlay-file: {exc}")
            raise typer.Exit(1) from None
        if not local:
            typer.echo("--overlay-file requires --local")
            raise typer.Exit(1)
    try:
        hud = (
            audit_local(path, base=base, use_cache=not no_cache, overlays=overlays)
            if local
            else audit_pr(path, base=base, use_cache=not no_cache)
        )
    except GitDiffError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None
    _emit_hud(hud, out, output_format)


@app.command()
def explain(
    local: Annotated[
        bool,
        typer.Option("--local", help="Explain working-tree + index changes vs a base branch."),
    ] = False,
    base: Annotated[
        str,
        typer.Option(help="Git base ref to diff against (default: main)."),
    ] = "main",
    path: Annotated[
        Path,
        typer.Option(exists=True, file_okay=False, help="Repository root to explain."),
    ] = Path("."),
    symbol: Annotated[
        str | None,
        typer.Option("--symbol", help="Only explain this symbol name."),
    ] = None,
    file: Annotated[
        str | None,
        typer.Option("--file", help="Only explain symbols in this repo-relative file path."),
    ] = None,
    why: Annotated[
        bool,
        typer.Option("--why", help="Show proven vs heuristic evidence for each sentence."),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format (markdown or json)."),
    ] = OutputFormat.markdown,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Bypass .focus-cache/ and re-parse every file."),
    ] = False,
) -> None:
    """Plain-English captions for changed symbols, with optional evidence trail."""
    mode = "local" if local else "range"
    try:
        context = build_explain_context(
            path,
            base=base,
            mode=mode,
            use_cache=not no_cache,
        )
    except GitDiffError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    if context is None:
        typer.echo(f"No changed symbols to explain vs `{base}`.")
        raise typer.Exit(0)

    symbols = context.symbols
    if file:
        normalized = file.replace("\\", "/")
        symbols = [s for s in symbols if s.path == normalized]
    if symbol:
        symbols = [s for s in symbols if s.name == symbol]

    if not symbols:
        typer.echo("No symbols matched your filters.")
        raise typer.Exit(1)

    filtered = ExplainContext(
        symbols=symbols,
        graph=context.graph,
        seeds=context.seeds,
        danger_paths=context.danger_paths,
        downstream_count=context.downstream_count,
        risk=context.risk,
        facts_by_path=context.facts_by_path,
    )
    explanations = explain_symbols(filtered)

    if output_format is OutputFormat.json:
        text = render_explanations_json(explanations, show_why=why)
    else:
        text = render_explanations_markdown(explanations, show_why=why)
    typer.echo(text.rstrip())


def _emit_hud(hud: FocusHUD, out: Path | None, fmt: OutputFormat) -> None:
    if fmt is OutputFormat.json:
        text = json.dumps(hud.model_dump(mode="json"), indent=2)
    else:
        text = render_hud(hud)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        typer.echo(f"Wrote Focus HUD to {out.resolve()}")
        if fmt is OutputFormat.markdown:
            typer.echo(
                "Open that file in the editor and use Markdown preview to see the diagram."
            )
    typer.echo(text)
