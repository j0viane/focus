"""Typer entrypoint for the Focus CLI."""

from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

import typer

from focus.graph import build_graph, downstream_rings
from focus.hud import build_hud, render_hud
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
    typer.echo(render_hud(hud))
