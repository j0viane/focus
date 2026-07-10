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
    """Everything the parser observed about one source file."""

    path: Path
    language: Literal["python", "javascript", "typescript"] = "python"
    imports: list[Import] = []
    definitions: list[Definition] = []
    calls: list[CallSite] = []


RiskTier = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
HudMode = Literal["full", "pass_through", "error"]


class ImpactNode(BaseModel):
    """One file in the blast radius, with hop distance from the seed."""

    path: str
    hops: int
    reason: str


class ChangedSymbolInfo(BaseModel):
    """A definition the diff actually touched (line overlap with a hunk)."""

    path: str
    name: str
    kind: Literal["function", "class"]
    line: int


class FocusHUD(BaseModel):
    """Canonical HUD payload — CLI and (later) PR comments render from this."""

    mode: HudMode
    seed: str
    summary: str
    risk_tier: RiskTier
    mermaid: str | None = None
    danger_zones: list[ImpactNode] = []
    downstream: list[ImpactNode] = []
    isolated: list[str] = []
    changed_symbols: list[ChangedSymbolInfo] = []
    caveat: str | None = None
