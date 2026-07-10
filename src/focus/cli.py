"""Typer entrypoint for the Focus CLI."""

from importlib.metadata import version as package_version

import typer

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
def scan(path: str = typer.Argument(".", help="Repository root to scan.")) -> None:
    """Index a repository and build its dependency graph."""
    # TODO(Week 1): walk `path`, respect .gitignore, collect Python files.
    typer.echo(f"scan: not implemented yet (target: {path})")
    raise typer.Exit(code=1)
