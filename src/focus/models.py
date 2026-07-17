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
    docstring: str | None = None


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
Confidence = Literal["proven", "heuristic"]
EvidenceKind = Literal[
    "diff_overlap",
    "docstring",
    "import",
    "call",
    "graph_importer",
    "downstream_count",
    "danger_path",
    "shared_hub",
    "heuristic_name",
    "heuristic_path",
    "symbol_registry",
    "test_module",
    "llm_label",
]


class ImpactNode(BaseModel):
    """One file in the blast radius, with hop distance from the seed."""

    path: str
    hops: int
    reason: str


class HunkDetail(BaseModel):
    """Inline explainer for one contiguous edit block inside a changed symbol."""

    line: int
    changed_lines: list[int] = []
    detail: str = ""


class EvidenceItem(BaseModel):
    """One verifiable or heuristic fact behind an explanation clause."""

    confidence: Confidence
    kind: EvidenceKind
    location: str
    fact: str


class ChangedSymbolInfo(BaseModel):
    """A definition the diff actually touched (line overlap with a hunk)."""

    path: str
    name: str
    kind: Literal["function", "class"]
    line: int
    changed_lines: list[int] = []
    summary: str = ""
    detail: str = ""
    explanation: str = ""
    # Risk rail: "{emoji} {RISK} — {who} — {what goes wrong}". Empty when quiet (LOW).
    implication: str = ""
    hunk_details: list[HunkDetail] = []
    # Proven/heuristic facts for IDE hover (not shown on the CodeLens line).
    evidence: list[EvidenceItem] = []


class ExplanationClause(BaseModel):
    """Purpose or impact sentence plus the evidence that produced it."""

    role: Literal["purpose", "impact"]
    text: str
    evidence: list[EvidenceItem] = []


class SymbolExplanation(BaseModel):
    """Full explanation for one changed symbol, optionally with evidence trail."""

    symbol: ChangedSymbolInfo
    text: str
    clauses: list[ExplanationClause] = []


class LineExplanation(BaseModel):
    """Inline explainer for a diff hunk outside any changed symbol body."""

    path: str
    line: int
    changed_lines: list[int] = []
    detail: str = ""


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
    line_explanations: list[LineExplanation] = []
    caveat: str | None = None
