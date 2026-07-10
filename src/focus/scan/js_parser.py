"""Tree-sitter extraction for JavaScript and TypeScript.

Maps ESM import/export and CommonJS require(...) into the same
``Import`` / ``Definition`` / ``CallSite`` models Python uses. Only
literals written in the file are recorded — no module resolution here.
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from focus.models import CallSite, Definition, Import, ModuleFacts

_JS_LANGUAGE = Language(tree_sitter_javascript.language())
_TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
_TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())

_JS_PARSER = Parser(_JS_LANGUAGE)
_TS_PARSER = Parser(_TS_LANGUAGE)
_TSX_PARSER = Parser(_TSX_LANGUAGE)

_JS_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs"})
_TS_EXTENSIONS = frozenset({".ts"})
_TSX_EXTENSIONS = frozenset({".tsx"})

SOURCE_EXTENSIONS = _JS_EXTENSIONS | _TS_EXTENSIONS | _TSX_EXTENSIONS


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
    parser = _parser_for(path)
    tree = parser.parse(source)
    root = tree.root_node
    return ModuleFacts(
        path=path,
        language=language_for_path(path),
        imports=_extract_imports(root),
        definitions=_extract_definitions(root),
        calls=_extract_calls(root),
    )


def _parser_for(path: Path) -> Parser:
    suffix = path.suffix.lower()
    if suffix in _TSX_EXTENSIONS:
        return _TSX_PARSER
    if suffix in _TS_EXTENSIONS:
        return _TS_PARSER
    if suffix in _JS_EXTENSIONS:
        return _JS_PARSER
    raise ValueError(f"Not a JS/TS path: {path}")


def _extract_imports(root: Node) -> list[Import]:
    imports: list[Import] = []
    for node in _walk(root):
        if node.type == "import_statement":
            imports.extend(_esm_import(node))
        elif node.type == "call_expression":
            req = _require_import(node)
            if req is not None:
                imports.append(req)
    return imports


def _esm_import(node: Node) -> list[Import]:
    source = _string_literal(node.child_by_field_name("source"))
    if not source:
        # tree-sitter may expose the path as a bare string child
        for child in node.children:
            if child.type == "string":
                source = _string_literal(child)
                break
    if not source:
        return []

    clause = None
    for child in node.children:
        if child.type == "import_clause":
            clause = child
            break

    if clause is None:
        return [Import(module=source, symbols=[], line=_line(node))]

    symbols: list[str] = []
    alias: str | None = None
    for child in clause.children:
        if child.type == "identifier":
            # default import
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

    return [Import(module=source, symbols=symbols, alias=alias, line=_line(node))]


def _require_import(node: Node) -> Import | None:
    fn = node.child_by_field_name("function")
    if fn is None or _text(fn) != "require":
        return None
    args = node.child_by_field_name("arguments")
    if args is None:
        return None
    for child in args.children:
        if child.type == "string":
            module = _string_literal(child)
            if module:
                return Import(module=module, symbols=[], line=_line(node))
    return None


def _extract_definitions(root: Node) -> list[Definition]:
    definitions: list[Definition] = []
    for node in _walk(root):
        if node.type == "function_declaration":
            name = node.child_by_field_name("name")
            if name is not None:
                definitions.append(
                    Definition(name=_text(name), kind="function", line=_line(name))
                )
        elif node.type == "class_declaration":
            name = node.child_by_field_name("name")
            if name is not None:
                definitions.append(
                    Definition(name=_text(name), kind="class", line=_line(name))
                )
    seen: set[tuple[str, int]] = set()
    unique: list[Definition] = []
    for d in sorted(definitions, key=lambda x: x.line):
        key = (d.name, d.line)
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def _extract_calls(root: Node) -> list[CallSite]:
    calls: list[CallSite] = []
    for node in _walk(root):
        if node.type != "call_expression":
            continue
        fn = node.child_by_field_name("function")
        if fn is None:
            continue
        callee = _text(fn)
        if callee == "require":
            continue
        calls.append(CallSite(callee=callee, line=_line(node)))
    return sorted(calls, key=lambda c: c.line)


def _string_literal(node: Node | None) -> str:
    if node is None:
        return ""
    raw = _text(node)
    if len(raw) >= 2 and raw[0] in {"'", '"', "`"} and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def _walk(root: Node):
    cursor = root.walk()
    visited = False
    while True:
        if not visited and cursor.goto_first_child():
            yield cursor.node
            continue
        if cursor.goto_next_sibling():
            visited = False
            yield cursor.node
            continue
        if not cursor.goto_parent():
            return
        visited = True


def _text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8")


def _line(node: Node) -> int:
    return node.start_point.row + 1
