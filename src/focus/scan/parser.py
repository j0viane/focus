"""Tree-sitter extraction of imports, definitions, and call sites.

Facts are read from source text only: nothing is executed, and nothing
is recorded that isn't literally written in the file. Resolution of
imports to files and calls to definitions happens later, in the graph
layer, where the whole-repo picture exists.
"""

from pathlib import Path

import tree_sitter_python
from tree_sitter import Language, Node, Parser, Query, QueryCursor

from focus.models import CallSite, Definition, Import, ModuleFacts

_LANGUAGE = Language(tree_sitter_python.language())
_PARSER = Parser(_LANGUAGE)

_DEFINITIONS_QUERY = Query(
    _LANGUAGE,
    """
    (function_definition name: (identifier) @function)
    (class_definition name: (identifier) @class)
    """,
)

_CALLS_QUERY = Query(_LANGUAGE, "(call function: (_) @callee)")


def parse_module(path: Path) -> ModuleFacts:
    """Parse one Python file into its observable facts."""
    return parse_source(path.read_bytes(), path)


def parse_source(source: bytes, path: Path) -> ModuleFacts:
    """Parse raw source bytes; `path` is recorded, not read."""
    tree = _PARSER.parse(source)
    root = tree.root_node
    return ModuleFacts(
        path=path,
        imports=_extract_imports(root),
        definitions=_extract_definitions(root),
        calls=_extract_calls(root),
    )


def _extract_imports(root: Node) -> list[Import]:
    imports: list[Import] = []
    for node in _walk(root):
        if node.type == "import_statement":
            imports.extend(_plain_import(node))
        elif node.type == "import_from_statement":
            imports.append(_from_import(node))
    return imports


def _plain_import(node: Node) -> list[Import]:
    """`import a.b, c as d` — one Import per comma-separated target."""
    imports = []
    for name_node in node.children_by_field_name("name"):
        if name_node.type == "aliased_import":
            module = _text(name_node.child_by_field_name("name"))
            alias = _text(name_node.child_by_field_name("alias"))
        else:
            module = _text(name_node)
            alias = None
        imports.append(Import(module=module, alias=alias, line=_line(node)))
    return imports


def _from_import(node: Node) -> Import:
    """`from a.b import c, d as e` / `from . import f` / `from a import *`."""
    module = _text(node.child_by_field_name("module_name"))
    symbols = []
    for name_node in node.children_by_field_name("name"):
        if name_node.type == "aliased_import":
            symbols.append(_text(name_node.child_by_field_name("name")))
        else:
            symbols.append(_text(name_node))
    if not symbols and any(child.type == "wildcard_import" for child in node.children):
        symbols = ["*"]
    return Import(module=module, symbols=symbols, line=_line(node))


def _extract_definitions(root: Node) -> list[Definition]:
    definitions = [
        Definition(name=_text(node), kind=capture, line=_line(node))  # type: ignore[arg-type]
        for capture, nodes in QueryCursor(_DEFINITIONS_QUERY).captures(root).items()
        for node in nodes
    ]
    return sorted(definitions, key=lambda d: d.line)


def _extract_calls(root: Node) -> list[CallSite]:
    calls = [
        CallSite(callee=_text(node), line=_line(node))
        for nodes in QueryCursor(_CALLS_QUERY).captures(root).values()
        for node in nodes
    ]
    return sorted(calls, key=lambda c: c.line)


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
