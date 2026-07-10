"""Build the repo-wide dependency graph from parsed module facts.

Nodes are files (posix paths relative to the scan root); a directed
edge A -> B means "A imports B". An edge exists only when the imported
module name resolves to a file that was actually scanned — stdlib,
node_modules, and third-party imports never create nodes or edges, so
the graph contains no invented topology.
"""

from __future__ import annotations

import posixpath
from pathlib import Path, PurePosixPath

import networkx as nx

from focus.models import Import, ModuleFacts
from focus.scan.js_parser import SOURCE_EXTENSIONS as JS_SOURCE_EXTENSIONS

_JS_SUFFIXES = tuple(sorted(JS_SOURCE_EXTENSIONS))


def build_graph(all_facts: list[ModuleFacts], root: Path) -> nx.DiGraph:
    """Connect scanned files into a directed 'imports' graph."""
    root = root.resolve()
    rel_facts = [(_relative(facts.path, root), facts) for facts in all_facts]
    modules = {_dotted(rel): rel for rel, _ in rel_facts}
    for rel, _ in rel_facts:
        # Conventional src layout: src/focus/models.py imports as focus.models.
        if rel.parts[0] == "src" and len(rel.parts) > 1:
            modules.setdefault(_dotted(PurePosixPath(*rel.parts[1:])), rel)

    js_index = _js_path_index([rel for rel, _ in rel_facts])

    graph = nx.DiGraph()
    for rel, facts in rel_facts:
        graph.add_node(str(rel))
        for imp in facts.imports:
            for target in _resolve(imp, rel, modules, js_index):
                if target != rel:
                    graph.add_edge(str(rel), str(target))
    return graph


def downstream_rings(graph: nx.DiGraph, target: str) -> list[tuple[int, list[str]]]:
    """Files that depend on `target`, grouped by import distance.

    Ring 1 imports the target directly; ring 2 imports ring 1; and so
    on. Computed by walking the import arrows backwards (reverse BFS).
    """
    distances = nx.single_source_shortest_path_length(graph.reverse(copy=False), target)
    rings: dict[int, list[str]] = {}
    for node, distance in distances.items():
        if distance > 0:
            rings.setdefault(distance, []).append(node)
    return [(distance, sorted(nodes)) for distance, nodes in sorted(rings.items())]


def _relative(path: Path, root: Path) -> PurePosixPath:
    if path.is_absolute():
        path = path.resolve().relative_to(root)
    return PurePosixPath(path.as_posix())


def _dotted(rel: PurePosixPath) -> str:
    """Module name a file answers to: billing/service.py -> billing.service."""
    parts = rel.parts[:-1] if rel.name == "__init__.py" else (*rel.parts[:-1], rel.stem)
    return ".".join(parts)


def _resolve(
    imp: Import,
    importer: PurePosixPath,
    modules: dict[str, PurePosixPath],
    js_index: dict[str, PurePosixPath],
):
    """Scanned files this import statement can refer to."""
    if _uses_js_resolution(imp.module, importer):
        target = _resolve_js_relative(imp.module, importer, js_index)
        if target is not None:
            yield target
        return

    base = _absolute_module_name(imp.module, importer)
    if base is None:
        return
    candidates = [base] if base else []
    candidates += [f"{base}.{s}" if base else s for s in imp.symbols if s != "*"]
    seen = set()
    for candidate in candidates:
        target = modules.get(candidate)
        if target is not None and target not in seen:
            seen.add(target)
            yield target


def _uses_js_resolution(module: str, importer: PurePosixPath) -> bool:
    if importer.suffix.lower() in JS_SOURCE_EXTENSIONS:
        return True
    return module.startswith("./") or module.startswith("../")


def _js_path_index(rels: list[PurePosixPath]) -> dict[str, PurePosixPath]:
    """Map normalized path keys → scanned JS/TS files."""
    index: dict[str, PurePosixPath] = {}
    for rel in rels:
        if rel.suffix.lower() not in JS_SOURCE_EXTENSIONS:
            continue
        index[str(rel)] = rel
        without = str(rel.with_suffix(""))
        index.setdefault(without, rel)
        if rel.stem == "index":
            index.setdefault(str(rel.parent), rel)
    return index


def _resolve_js_relative(
    module: str,
    importer: PurePosixPath,
    js_index: dict[str, PurePosixPath],
) -> PurePosixPath | None:
    """Resolve `./foo` / `../bar` against scanned JS/TS files only."""
    if not (module.startswith("./") or module.startswith("../")):
        return None
    joined = posixpath.normpath(str(importer.parent / module))
    if joined in js_index:
        return js_index[joined]
    for suffix in _JS_SUFFIXES:
        candidate = joined + suffix
        if candidate in js_index:
            return js_index[candidate]
    for suffix in _JS_SUFFIXES:
        candidate = f"{joined}/index{suffix}"
        if candidate in js_index:
            return js_index[candidate]
    return None


def _absolute_module_name(module: str, importer: PurePosixPath) -> str | None:
    """Turn a possibly-relative module string into an absolute dotted name.

    ".sibling" inside pkg/mod.py -> "pkg.sibling"; a relative import
    that climbs above the scan root resolves to None.
    """
    if not module.startswith("."):
        return module
    dots = len(module) - len(module.lstrip("."))
    remainder = module[dots:]
    package = importer.parts[:-1]
    if dots - 1 > len(package):
        return None
    prefix = package[: len(package) - (dots - 1)]
    parts = [*prefix, remainder] if remainder else list(prefix)
    return ".".join(parts)
