"""JS/TS parser + glass_box_js graph — Phase 3 multi-language slice."""

from pathlib import Path

from focus.graph import build_graph, downstream_rings
from focus.hud import build_hud
from focus.hud.classify import is_danger_zone
from focus.scan import discover_source_files, parse_module, parse_source


def test_ts_import_shapes():
    facts = parse_source(
        b"import { validateToken } from './authUtils';\n",
        Path("billing/service.ts"),
    )
    assert facts.language == "typescript"
    assert len(facts.imports) == 1
    assert facts.imports[0].module == "./authUtils"
    assert facts.imports[0].symbols == ["validateToken"]


def test_js_require_import():
    facts = parse_source(
        b"const auth = require('../authUtils');\n",
        Path("billing/service.js"),
    )
    assert facts.language == "javascript"
    assert facts.imports[0].module == "../authUtils"


def test_ts_definitions_and_exports():
    facts = parse_source(
        b"export function chargeUser() {}\nexport class Router {}\n",
        Path("api/routes.ts"),
    )
    names = {d.name for d in facts.definitions}
    assert "chargeUser" in names
    assert "Router" in names


def test_ts_nested_calls_do_not_segfault_or_emit_garbage_lines():
    """Regression: TreeCursor walks produced stale nodes → SIGSEGV in Pydantic."""
    # Nested registerCommand / then / withProgress style (extension.ts shape).
    src = b"""
import * as vscode from "vscode";

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("focus.auditLocal", () => runAudit()),
    vscode.commands.registerCommand("focus.showWhy", (reason?: string) => {
      void vscode.window
        .showInformationMessage(`Focus: ${reason}`, "Open HUD")
        .then((pick) => {
          if (pick === "Open HUD") {
            HudPanel.show();
          }
        });
    }),
  );
  void (async () => {
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Window, title: "Focus" },
      () => auditLocal(),
    );
  })();
}
"""
    facts = parse_source(src, Path("extensions/vscode-focus/src/extension.ts"))
    assert facts.language == "typescript"
    max_line = src.count(b"\n") + 1
    assert all(1 <= c.line <= max_line for c in facts.calls)
    assert any("registerCommand" in c.callee for c in facts.calls)


def test_real_extension_ts_parses_without_crash():
    path = Path("extensions/vscode-focus/src/extension.ts")
    if not path.is_file():
        return
    facts = parse_module(path)
    assert facts.language == "typescript"
    text = path.read_bytes()
    max_line = text.count(b"\n") + 1
    assert all(1 <= c.line <= max_line for c in facts.calls)



def test_discovers_glass_box_js(glass_box_js_path: Path):
    files = discover_source_files(glass_box_js_path)
    rels = sorted(f.relative_to(glass_box_js_path.resolve()).as_posix() for f in files)
    assert rels == [
        "api/routes.ts",
        "authUtils.ts",
        "billing/service.ts",
        "dashboard/views.ts",
        "jobs/worker.ts",
    ]


def test_glass_box_js_edges(glass_box_js_path: Path):
    facts = [parse_module(f) for f in discover_source_files(glass_box_js_path)]
    graph = build_graph(facts, glass_box_js_path)
    assert set(graph.edges()) == {
        ("billing/service.ts", "authUtils.ts"),
        ("dashboard/views.ts", "authUtils.ts"),
        ("jobs/worker.ts", "authUtils.ts"),
        ("api/routes.ts", "billing/service.ts"),
    }


def test_glass_box_js_blast_radius(glass_box_js_path: Path):
    facts = [parse_module(f) for f in discover_source_files(glass_box_js_path)]
    graph = build_graph(facts, glass_box_js_path)
    assert downstream_rings(graph, "authUtils.ts") == [
        (1, ["billing/service.ts", "dashboard/views.ts", "jobs/worker.ts"]),
        (2, ["api/routes.ts"]),
    ]
    assert is_danger_zone("authUtils.ts", graph) is True
    assert is_danger_zone("api/routes.ts", graph) is True

    hud = build_hud(graph, "authUtils.ts", downstream_rings(graph, "authUtils.ts"))
    assert hud.mode == "full"
    assert any(n.path == "api/routes.ts" for n in hud.danger_zones)


def test_bare_package_import_creates_no_edge(tmp_path: Path):
    src = tmp_path / "app.ts"
    src.write_text("import lodash from 'lodash';\n", encoding="utf-8")
    facts = [parse_module(src)]
    graph = build_graph(facts, tmp_path)
    assert list(graph.nodes()) == ["app.ts"]
    assert list(graph.edges()) == []
