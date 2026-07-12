import * as path from "node:path";
import * as vscode from "vscode";

import type { ChangedSymbolInfo, FocusHUD, ImpactNode } from "./types";

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
    const rel = relPath(this.root, document.uri.fsPath);
    if (!rel) {
      return [];
    }

    const lenses: vscode.CodeLens[] = [];
    const symbols = this.hud.changed_symbols.filter((s) => s.path === rel);

    for (const sym of symbols) {
      lenses.push(symbolLens(this.hud, sym));
    }

    if (symbols.length > 0) {
      return lenses;
    }

    const fileLens = blastRadiusLens(this.hud, rel);
    if (fileLens) {
      lenses.push(fileLens);
    }
    return lenses;
  }
}

function relPath(root: string, fsPath: string): string | undefined {
  const rel = path.relative(root, fsPath).split(path.sep).join("/");
  if (!rel || rel.startsWith("..")) {
    return undefined;
  }
  return rel;
}

function symbolLens(hud: FocusHUD, sym: ChangedSymbolInfo): vscode.CodeLens {
  const line = Math.max(0, sym.line - 1);
  const n = hud.downstream.length;
  return new vscode.CodeLens(new vscode.Range(line, 0, line, 0), {
    title: `Focus · changed · ${sym.name} · ${hud.risk_tier} · ${n} downstream`,
    command: "focus.showHud",
    tooltip: `${sym.kind} ${sym.name} — ${hud.summary}`,
  });
}

function blastRadiusLens(hud: FocusHUD, rel: string): vscode.CodeLens | undefined {
  const danger = lookupNode(hud.danger_zones, rel);
  const downstream = lookupNode(hud.downstream, rel);
  const n = hud.downstream.length;
  const isSeed =
    hud.seed === rel ||
    hud.seed.endsWith("/" + rel) ||
    rel.endsWith(hud.seed) ||
    seedPaths(hud.seed).includes(rel);

  let title: string | undefined;
  let reason: string | undefined;

  if (isSeed) {
    title = `Focus · ${hud.risk_tier} · ${n} downstream`;
    reason = hud.summary;
  } else if (danger) {
    title = `Focus · Danger Zone · ${hud.risk_tier}`;
    reason = danger.reason;
  } else if (downstream) {
    title = `Focus · ${downstream.hops} hops from change`;
    reason = downstream.reason;
  }

  if (!title) {
    return undefined;
  }

  return new vscode.CodeLens(new vscode.Range(0, 0, 0, 0), {
    title,
    command: reason ? "focus.showWhy" : "focus.showHud",
    arguments: reason ? [reason] : undefined,
    tooltip: reason ?? hud.summary,
  });
}

function lookupNode(nodes: ImpactNode[], rel: string): ImpactNode | undefined {
  return nodes.find((n) => n.path === rel);
}

function seedPaths(seed: string): string[] {
  if (!seed || seed.startsWith("(")) {
    return [];
  }
  return seed.split(",").map((s) => s.trim()).filter(Boolean);
}
