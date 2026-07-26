"""Portable edit facts from the *target* repo's AST (Phase 4d thin slice).

Def–use chains for module-level names: where a constant is written (def),
where it is read in the same file (use), and which files import it (who).
Every fact is computed from the analyzed tree — no product-specific dictionaries.
"""

from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from focus.models import ModuleFacts

# ROA — captions stay short; prefer one sharp signal over a novel.
_MAX_RHS = 40
_MAX_CAPTION = 120
_MAX_IMPORTERS = 8


class AssignFact(BaseModel):
    """One module-level name binding observed in source."""

    name: str
    line: int
    end_line: int
    rhs: str


class ReaderFact(BaseModel):
    """One same-file Load of a name, attributed to an enclosing def."""

    name: str
    line: int


def module_level_assignments(source_text: str) -> list[AssignFact]:
    """Module-body assignments / annotated assignments with a value."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return []
    out: list[AssignFact] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            rhs = _rhs_text(source_text, node.value)
            end = getattr(node, "end_lineno", None) or node.lineno
            for target in node.targets:
                for name in _target_names(target):
                    out.append(
                        AssignFact(name=name, line=node.lineno, end_line=end, rhs=rhs)
                    )
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if not isinstance(node.target, ast.Name):
                continue
            rhs = _rhs_text(source_text, node.value)
            end = getattr(node, "end_lineno", None) or node.lineno
            out.append(
                AssignFact(
                    name=node.target.id,
                    line=node.lineno,
                    end_line=end,
                    rhs=rhs,
                )
            )
    return out


def same_file_readers(name: str, source_text: str) -> list[ReaderFact]:
    """Functions/classes in this file that Load ``name`` (def–use chain)."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return []
    visitor = _ReaderVisitor(name)
    visitor.visit(tree)
    return visitor.readers


def importers_of_name(
    name: str,
    changed_path: str,
    facts_by_path: dict[str, ModuleFacts],
) -> list[str]:
    """Repo files whose import facts pull ``name`` from the changed module."""
    seed_stem = PurePosixPath(changed_path).stem
    found: list[str] = []
    for path, facts in facts_by_path.items():
        if _paths_same(path, changed_path):
            continue
        for imp in facts.imports:
            if _import_references_symbol(imp.module, imp.symbols, name, seed_stem):
                found.append(path)
                break
        if len(found) >= _MAX_IMPORTERS:
            break
    return found


def scope_caption_for_module_assign(
    assign: AssignFact,
    *,
    readers: list[ReaderFact],
    importers: list[str],
) -> str | None:
    """Template caption from facts. None when there is no who/use to attach."""
    if not readers and not importers:
        return None
    clause = _reader_clause(readers) if readers else _importer_clause(importers)
    # ROA cap: shrink the RHS to make room — never slice the who-clause mid-word.
    rhs_budget = max(_MAX_CAPTION - len(f"Sets `{assign.name}` to `` — {clause}"), 8)
    rhs = _clip(assign.rhs, min(_MAX_RHS, rhs_budget))
    caption = f"Sets `{assign.name}` to `{rhs}` — {clause}"
    # Prefer readers; append importer count only when it still fits.
    if readers and importers and len(caption) + 28 <= _MAX_CAPTION:
        plural = "s" if len(importers) != 1 else ""
        caption = f"{caption}; imported by {len(importers)} file{plural}"
    return caption


def caption_for_overlapping_module_assign(
    *,
    source_text: str,
    hunk_lines: list[int],
    changed_path: str = "",
    facts_by_path: dict[str, ModuleFacts] | None = None,
) -> str | None:
    """If the orphan hunk overlaps a module-level assign with scope, caption it."""
    if not source_text or not hunk_lines:
        return None
    hunk = set(hunk_lines)
    assigns = [
        a
        for a in module_level_assignments(source_text)
        if any(a.line <= line <= a.end_line for line in hunk)
    ]
    if not assigns:
        return None
    # Prefer the assign whose span starts first in the hunk.
    assign = min(assigns, key=lambda a: (a.line, a.name))
    readers = same_file_readers(assign.name, source_text)
    importers = (
        importers_of_name(assign.name, changed_path, facts_by_path)
        if changed_path and facts_by_path
        else []
    )
    return scope_caption_for_module_assign(
        assign, readers=readers, importers=importers
    )


def _target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in target.elts:
            names.extend(_target_names(elt))
        return names
    return []


def _rhs_text(source: str, value: ast.AST) -> str:
    seg = ast.get_source_segment(source, value)
    if seg:
        return " ".join(seg.split())
    return "…"


def _clip(text: str, max_len: int) -> str:
    plain = " ".join(text.split())
    if len(plain) <= max_len:
        return plain
    cut = plain[: max_len - 1]
    for sep in (" ", ",", "(", ")"):
        idx = cut.rfind(sep)
        if idx >= max_len // 2:
            cut = cut[: idx + (1 if sep in "()" else 0)].rstrip(" ,")
            break
    return cut.rstrip() + "…"


def _reader_clause(readers: list[ReaderFact]) -> str:
    # Dedupe by enclosing name, keep first-seen order.
    seen: list[str] = []
    for reader in readers:
        if reader.name not in seen:
            seen.append(reader.name)
    if len(seen) == 1:
        return f"read by `{seen[0]}` in this file"
    return f"read by `{seen[0]}` and {len(seen) - 1} more in this file"


def _importer_clause(importers: list[str]) -> str:
    short = _short_path(importers[0])
    if len(importers) == 1:
        return f"imported by `{short}`"
    return f"imported by `{short}` and {len(importers) - 1} more"


def _short_path(path: str) -> str:
    name = PurePosixPath(path).name
    parent = PurePosixPath(path).parent.name
    if parent and parent not in {".", "src"}:
        return f"{parent}/{name}"
    return name


def _paths_same(a: str, b: str) -> bool:
    return Path(a).as_posix() == Path(b).as_posix()


def _import_references_symbol(
    module: str,
    symbols: list[str],
    symbol_name: str,
    seed_stem: str,
) -> bool:
    if symbol_name not in symbols and "*" not in symbols:
        return False
    mod = module.replace("/", ".").strip(".")
    if not mod:
        return True
    return seed_stem in mod.split(".") or mod.endswith(seed_stem)


class _ReaderVisitor(ast.NodeVisitor):
    """Attribute Name Loads of ``target`` to the innermost enclosing def."""

    def __init__(self, target: str) -> None:
        self.target = target
        self.scope: list[str] = []
        self.readers: list[ReaderFact] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Name(self, node: ast.Name) -> None:
        if (
            node.id == self.target
            and isinstance(node.ctx, ast.Load)
            and self.scope
        ):
            self.readers.append(ReaderFact(name=self.scope[-1], line=node.lineno))
