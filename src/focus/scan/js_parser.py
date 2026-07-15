"""Tree-sitter extraction for JavaScript and TypeScript.

Maps ESM import/export and CommonJS require(...) into the same
``Import`` / ``Definition`` / ``CallSite`` models Python uses. Only
literals written in the file are recorded — no module resolution here.

JS/TS parsing runs in a **subprocess** by default. Tree-sitter native
bindings can SIGSEGV on some TypeScript files; killing the audit process
would make Focus unusable. A dead worker → empty facts for that file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from focus.models import CallSite, Definition, Import, ModuleFacts

_JS_LANGUAGE = Language(tree_sitter_javascript.language())
_TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
_TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())

_JS_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs"})
_TS_EXTENSIONS = frozenset({".ts"})
_TSX_EXTENSIONS = frozenset({".tsx"})

SOURCE_EXTENSIONS = _JS_EXTENSIONS | _TS_EXTENSIONS | _TSX_EXTENSIONS

# Set FOCUS_JS_PARSE_INPROCESS=1 to skip the worker (tests / debugging only).
_ENV_INPROCESS = "FOCUS_JS_PARSE_INPROCESS"


def language_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _TSX_EXTENSIONS:
        return "typescript"
    if suffix in _TS_EXTENSIONS:
        return "typescript"
    if suffix in _JS_EXTENSIONS:
        return "javascript"
    raise ValueError(f"Not a JS/TS path: {path}")


def parse_js_source(source: bytes, path: Path) -> ModuleFacts:
    """Parse JS/TS source bytes into module facts."""
    empty = ModuleFacts(path=path, language=language_for_path(path))
    if os.environ.get(_ENV_INPROCESS) == "1":
        return _parse_js_source_inprocess(source, path) or empty

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "focus.scan.js_parser", str(path)],
            input=source,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return empty

    # 139 = SIGSEGV on Unix — worker died; skip this file, keep audit alive.
    if proc.returncode != 0 or not proc.stdout.strip():
        return empty

    try:
        payload = json.loads(proc.stdout.decode("utf-8"))
        return ModuleFacts(
            path=path,
            language=payload["language"],
            imports=[Import(**row) for row in payload.get("imports", [])],
            definitions=[Definition(**row) for row in payload.get("definitions", [])],
            calls=[CallSite(**row) for row in payload.get("calls", [])],
        )
    except Exception:
        return empty


def _parse_js_source_inprocess(source: bytes, path: Path) -> ModuleFacts | None:
    """In-process parse — may SIGSEGV; prefer ``parse_js_source`` (subprocess)."""
    parser = _parser_for(path)
    tree = parser.parse(source)
    root = tree.root_node
    max_line = max(1, source.count(b"\n") + 1)
    try:
        raw_imports = _extract_imports(root, max_line=max_line)
        raw_definitions = _extract_definitions(root, max_line=max_line)
        raw_calls = _extract_calls(root, max_line=max_line)
    except Exception:
        return None
    finally:
        del tree

    try:
        return ModuleFacts(
            path=path,
            language=language_for_path(path),
            imports=[Import(**row) for row in raw_imports],
            definitions=[Definition(**row) for row in raw_definitions],
            calls=[CallSite(**row) for row in raw_calls],
        )
    except Exception:
        return None


def _parser_for(path: Path) -> Parser:
    """Return a **new** Parser — do not reuse instances across files."""
    suffix = path.suffix.lower()
    if suffix in _TSX_EXTENSIONS:
        return Parser(_TSX_LANGUAGE)
    if suffix in _TS_EXTENSIONS:
        return Parser(_TS_LANGUAGE)
    if suffix in _JS_EXTENSIONS:
        return Parser(_JS_LANGUAGE)
    raise ValueError(f"Not a JS/TS path: {path}")


def _extract_imports(root: Node, *, max_line: int) -> list[dict]:
    imports: list[dict] = []
    for node in _walk(root):
        if node.type == "import_statement":
            imports.extend(_esm_import(node, max_line=max_line))
        elif node.type == "call_expression":
            req = _require_import(node, max_line=max_line)
            if req is not None:
                imports.append(req)
    return imports


def _esm_import(node: Node, *, max_line: int) -> list[dict]:
    source = _string_literal(node.child_by_field_name("source"))
    if not source:
        for child in node.children:
            if child.type == "string":
                source = _string_literal(child)
                break
    if not source:
        return []

    line = _safe_line(node, max_line=max_line)
    if line is None:
        return []

    clause = None
    for child in node.children:
        if child.type == "import_clause":
            clause = child
            break

    if clause is None:
        return [{"module": source, "symbols": [], "line": line}]

    symbols: list[str] = []
    alias: str | None = None
    for child in clause.children:
        if child.type == "identifier":
            symbols.append(_text(child))
        elif child.type == "named_imports":
            for spec in child.children:
                if spec.type == "import_specifier":
                    name = spec.child_by_field_name("name")
                    if name is not None:
                        symbols.append(_text(name))
        elif child.type == "namespace_import":
            symbols.append("*")
            for part in child.children:
                if part.type == "identifier":
                    alias = _text(part)

    return [{"module": source, "symbols": symbols, "alias": alias, "line": line}]


def _require_import(node: Node, *, max_line: int) -> dict | None:
    fn = node.child_by_field_name("function")
    if fn is None or _text(fn) != "require":
        return None
    args = node.child_by_field_name("arguments")
    if args is None:
        return None
    line = _safe_line(node, max_line=max_line)
    if line is None:
        return None
    for child in args.children:
        if child.type == "string":
            module = _string_literal(child)
            if module:
                return {"module": module, "symbols": [], "line": line}
    return None


def _extract_definitions(root: Node, *, max_line: int) -> list[dict]:
    definitions: list[dict] = []
    for node in _walk(root):
        if node.type == "function_declaration":
            name = node.child_by_field_name("name")
            if name is not None:
                line = _safe_line(name, max_line=max_line)
                if line is not None:
                    definitions.append(
                        {"name": _text(name), "kind": "function", "line": line}
                    )
        elif node.type == "class_declaration":
            name = node.child_by_field_name("name")
            if name is not None:
                line = _safe_line(name, max_line=max_line)
                if line is not None:
                    definitions.append(
                        {"name": _text(name), "kind": "class", "line": line}
                    )
    seen: set[tuple[str, int]] = set()
    unique: list[dict] = []
    for d in sorted(definitions, key=lambda x: x["line"]):
        key = (d["name"], d["line"])
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def _extract_calls(root: Node, *, max_line: int) -> list[dict]:
    calls: list[dict] = []
    for node in _walk(root):
        if node.type != "call_expression":
            continue
        fn = node.child_by_field_name("function")
        if fn is None:
            continue
        callee = _text(fn)
        if not callee or callee == "require":
            continue
        line = _safe_line(node, max_line=max_line)
        if line is None:
            continue
        calls.append({"callee": callee, "line": line})
    return sorted(calls, key=lambda c: c["line"])


def _string_literal(node: Node | None) -> str:
    if node is None:
        return ""
    raw = _text(node)
    if len(raw) >= 2 and raw[0] in {"'", '"', "`"} and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def _walk(root: Node):
    """Depth-first walk via ``children`` (not TreeCursor)."""
    stack: list[Node] = [root]
    while stack:
        node = stack.pop()
        yield node
        children = node.children
        for child in reversed(children):
            stack.append(child)


def _text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8")


def _safe_line(node: Node, *, max_line: int) -> int | None:
    """Return a 1-based line inside the file, or None if the node looks corrupt."""
    try:
        line = int(node.start_point.row) + 1
    except Exception:
        return None
    if line < 1 or line > max_line:
        return None
    return line


def _worker_main() -> None:
    """stdin = source bytes; argv[1] = path; stdout = JSON facts."""
    if len(sys.argv) < 2:
        sys.exit(2)
    path = Path(sys.argv[1])
    source = sys.stdin.buffer.read()
    os.environ[_ENV_INPROCESS] = "1"
    facts = _parse_js_source_inprocess(source, path)
    if facts is None:
        sys.exit(1)
    payload = {
        "language": facts.language,
        "imports": [i.model_dump(mode="json") for i in facts.imports],
        "definitions": [d.model_dump(mode="json") for d in facts.definitions],
        "calls": [c.model_dump(mode="json") for c in facts.calls],
    }
    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    _worker_main()
