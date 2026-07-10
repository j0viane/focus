"""Extract imports, definitions, and call sites from source files.

Python uses the stdlib ``ast`` module (no native extension) so a bad
parse cannot segfault the process. JS/TS still goes through Tree-sitter
in ``js_parser``. Facts are read from source text only: nothing is
executed, and nothing is recorded that isn't literally written in the
file. Resolution of imports to files happens later in the graph layer.
"""

from __future__ import annotations

import ast
from pathlib import Path

from focus.models import CallSite, Definition, Import, ModuleFacts
from focus.scan.js_parser import SOURCE_EXTENSIONS as JS_SOURCE_EXTENSIONS
from focus.scan.js_parser import parse_js_source

_PYTHON_EXTENSIONS = frozenset({".py"})


def parse_module(path: Path) -> ModuleFacts:
    """Parse one source file into its observable facts."""
    return parse_source(path.read_bytes(), path)


def parse_source(source: bytes, path: Path) -> ModuleFacts:
    """Parse raw source bytes; `path` selects the grammar and is recorded."""
    suffix = path.suffix.lower()
    if suffix in JS_SOURCE_EXTENSIONS:
        return parse_js_source(source, path)
    if suffix in _PYTHON_EXTENSIONS or suffix == "":
        return _parse_python(source, path)
    raise ValueError(f"Unsupported source language for {path}")


def _parse_python(source: bytes, path: Path) -> ModuleFacts:
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError:
        text = source.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Broken files must not crash Focus; return empty facts.
        return ModuleFacts(path=path, language="python")
    return ModuleFacts(
        path=path,
        language="python",
        imports=_extract_imports(tree),
        definitions=_extract_definitions(tree),
        calls=_extract_calls(tree),
    )


def _extract_imports(tree: ast.AST) -> list[Import]:
    imports: list[Import] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    Import(
                        module=alias.name,
                        alias=alias.asname,
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            imports.append(_from_import(node))
    return imports


def _from_import(node: ast.ImportFrom) -> Import:
    """`from a.b import c, d as e` / `from . import f` / `from a import *`."""
    level = node.level or 0
    module = ("." * level) + (node.module or "")
    symbols: list[str] = []
    for alias in node.names:
        if alias.name == "*":
            symbols = ["*"]
            break
        symbols.append(alias.name)
    return Import(module=module, symbols=symbols, line=node.lineno)


def _extract_definitions(tree: ast.AST) -> list[Definition]:
    definitions: list[Definition] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.append(
                Definition(name=node.name, kind="function", line=node.lineno)
            )
        elif isinstance(node, ast.ClassDef):
            definitions.append(
                Definition(name=node.name, kind="class", line=node.lineno)
            )
    return sorted(definitions, key=lambda d: d.line)


def _extract_calls(tree: ast.AST) -> list[CallSite]:
    calls: list[CallSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _callee_as_written(node.func)
        if callee:
            calls.append(CallSite(callee=callee, line=node.lineno))
    return sorted(calls, key=lambda c: c.line)


def _callee_as_written(func: ast.AST) -> str:
    """Callee text as written: ``print``, ``os.getcwd``, ``foo.bar.baz``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _callee_as_written(func.value)
        if not base:
            return ""
        return f"{base}.{func.attr}"
    # Subscript / call-as-callee / lambda — skip; not a stable name.
    return ""
