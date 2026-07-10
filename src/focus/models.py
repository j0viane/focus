"""Typed facts extracted from source files.

These models are the contract between the parser (which produces them)
and the dependency graph (which consumes them). Everything here is a
plain, verifiable observation about the text of one file — no inference,
no execution, no LLM.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class Import(BaseModel):
    """One import statement binding.

    `module` is the dotted path exactly as written, including leading
    dots for relative imports (".sibling", "."). `symbols` lists the
    names pulled in by a `from` import; it is empty for `import x` and
    `["*"]` for wildcard imports.
    """

    module: str
    symbols: list[str] = []
    alias: str | None = None
    line: int


class Definition(BaseModel):
    """A function or class this file defines."""

    name: str
    kind: Literal["function", "class"]
    line: int


class CallSite(BaseModel):
    """Something this file invokes, as written ("charge_user", "os.getcwd")."""

    callee: str
    line: int


class ModuleFacts(BaseModel):
    """Everything the parser observed about one Python file."""

    path: Path
    imports: list[Import] = []
    definitions: list[Definition] = []
    calls: list[CallSite] = []
