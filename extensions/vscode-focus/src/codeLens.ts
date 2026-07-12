import * as path from "node:path";
import * as vscode from "vscode";

import type { FocusHUD } from "./types";

export class FocusCodeLensProvider implements vscode.CodeLensProvider {
  private _onDidChange = new vscode.EventEmitter<void>();
  readonly onDidChangeCodeLenses = this._onDidChange.event;

  private hud: FocusHUD | undefined;
  private root: string | undefined;

  refresh(hud: FocusHUD | undefined, root: string | undefined): void {
    this.hud = hud;
    this.root = root;
    this._onDidChange.fire();
  }

  provideCodeLenses(
    document: vscode.TextDocument,
  ): vscode.ProviderResult<vscode.CodeLens[]> {
    if (!this.hud || !this.root) {
      return [];
    }
    const rel = path.relative(this.root, document.uri.fsPath).split(path.sep).join("/");
    if (!rel || rel.startsWith("..")) {
      return [];
    }

    const label = lensLabel(this.hud, rel);
    if (!label) {
      return [];
    }

    const range = new vscode.Range(0, 0, 0, 0);
    return [
      new vscode.CodeLens(range, {
        title: label,
        command: "focus.showHud",
        tooltip: this.hud.summary,
      }),
    ];
  }
}

function lensLabel(hud: FocusHUD, rel: string): string | undefined {
  const n = hud.downstream.length;
  const dangerPaths = new Set(hud.danger_zones.map((z) => z.path));
  const downPaths = new Set(hud.downstream.map((z) => z.path));

  const isSeed =
    hud.seed === rel ||
    hud.seed.endsWith("/" + rel) ||
    rel.endsWith(hud.seed) ||
    hud.changed_symbols.some((s) => s.path === rel);

  if (isSeed) {
    return `Focus · ${hud.risk_tier} · ${n} downstream`;
  }
  if (dangerPaths.has(rel)) {
    return `Focus · Danger Zone · ${hud.risk_tier}`;
  }
  if (downPaths.has(rel)) {
    const node = hud.downstream.find((z) => z.path === rel);
    return `Focus · ${node?.hops ?? "?"} hops from change`;
  }
  return undefined;
}
