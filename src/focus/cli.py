"""Typer entrypoint for the Focus CLI."""

from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

import typer

from focus.scan import discover_python_files

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
    """Discover the Python files Focus will index (respects .gitignore)."""
    files = discover_python_files(path)
    root = path.resolve()
    for file in files:
        typer.echo(file.relative_to(root).as_posix())
    typer.echo(f"{len(files)} Python file(s) found")
