"""Typer entrypoint for the Focus CLI."""

from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

import typer

from focus.audit import audit_local
from focus.graph import build_graph, downstream_rings
from focus.hud import build_hud, render_hud
from focus.ingest import GitDiffError
from focus.models import FocusHUD
from focus.scan import discover_python_files, parse_module

app = typer.Typer(
    name="focus",
    help="Architectural diagnostic engine — blast radius before merge.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed Focus version."""
    typer.echo(package_version("focus"))


@app.command()
def scan(
    path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, help="Repository root to scan."),
    ] = Path("."),
) -> None:
    """Index the repo's Python files: imports, definitions, calls per file."""
    files = discover_python_files(path)
    root = path.resolve()
    total_imports = total_defs = total_calls = 0
    for file in files:
        facts = parse_module(file)
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
        f"{len(files)} Python file(s) indexed: "
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
        typer.Option("--out", help="Write HUD markdown here (open in IDE preview)."),
    ] = None,
) -> None:
    """Show the Focus HUD for FILE: summary, Mermaid map, blast radius rings."""
    try:
        target = file.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        typer.echo(f"{file} is not inside the scan root {root.resolve()}")
        raise typer.Exit(1) from None

    facts = [parse_module(f) for f in discover_python_files(root)]
    graph = build_graph(facts, root)
    if target not in graph:
        typer.echo(f"{target} was not among the scanned Python files under {root.resolve()}")
        raise typer.Exit(1)

    rings = downstream_rings(graph, target)
    hud = build_hud(graph, target, rings)
    _emit_hud(hud, out)


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
        typer.Option("--out", help="Write HUD markdown here (open in IDE preview)."),
    ] = None,
) -> None:
    """Pre-merge blast radius for local changes (Phase 2) or a PR (Phase 3)."""
    if not local:
        typer.echo("Pass --local to audit your working tree. PR audit lands in Phase 3.")
        raise typer.Exit(2)

    try:
        hud = audit_local(path, base=base)
    except GitDiffError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None
    _emit_hud(hud, out)


def _emit_hud(hud: FocusHUD, out: Path | None) -> None:
    text = render_hud(hud)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        typer.echo(f"Wrote Focus HUD to {out.resolve()}")
        typer.echo("Open that file in the editor and use Markdown preview to see the diagram.")
    typer.echo(text)
