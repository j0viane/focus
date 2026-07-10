"""Typer entrypoint for the Focus CLI."""

from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

import typer

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
