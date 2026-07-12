import * as path from "node:path";
import * as vscode from "vscode";

import { definitionLine, editorLine, hunkDetailsForSymbol } from "./symbolLayout";
import { FOCUS_BADGE, riskEmoji } from "./icons";
import { explanationLensTitle, summaryLensTitle } from "./explainText";
import { inlineExplanationsEnabled } from "./inlineExplanation";
import type { ChangedSymbolInfo, FocusHUD, ImpactNode, LineExplanation, RiskTier } from "./types";

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
      lenses.push(...symbolLenses(document, this.hud, sym));
    }

    for (const note of this.hud.line_explanations ?? []) {
      if (note.path === rel) {
        lenses.push(...orphanLineLenses(document, note));
      }
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

function symbolLenses(
  document: vscode.TextDocument,
  hud: FocusHUD,
  sym: ChangedSymbolInfo,
): vscode.CodeLens[] {
  const defLine = definitionLine(sym);
  const n = hud.downstream.length;
  const badge = `${FOCUS_BADGE} Focus · ${sym.name} · ${riskEmoji(hud.risk_tier)} ${hud.risk_tier} · ${n} downstream`;
  const headerTitle = sym.summary ? `${badge}\n${summaryLensTitle(sym.summary)}` : badge;

  const lenses: vscode.CodeLens[] = [
    new vscode.CodeLens(new vscode.Range(defLine, 0, defLine, 0), {
      title: headerTitle,
      command: "focus.noop",
      tooltip: sym.summary ?? sym.explanation ?? `${sym.kind} ${sym.name} — ${hud.summary}`,
    }),
  ];

  if (inlineExplanationsEnabled()) {
    for (const hunk of hunkDetailsForSymbol(sym)) {
      const line = editorLine(hunk.line);
      if (line >= document.lineCount || !hunk.detail) {
        continue;
      }
      lenses.push(
        new vscode.CodeLens(new vscode.Range(line, 0, line, 0), {
          title: explanationLensTitle(hunk.detail),
          command: "focus.noop",
          tooltip: sym.explanation ?? hunk.detail,
        }),
      );
    }
  }

  return lenses;
}

function orphanLineLenses(
  document: vscode.TextDocument,
  note: LineExplanation,
): vscode.CodeLens[] {
  if (!inlineExplanationsEnabled() || !note.detail) {
    return [];
  }
  const line = editorLine(note.line);
  if (line >= document.lineCount) {
    return [];
  }
  return [
    new vscode.CodeLens(new vscode.Range(line, 0, line, 0), {
      title: explanationLensTitle(note.detail),
      command: "focus.noop",
      tooltip: note.detail,
    }),
  ];
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
    title = `${FOCUS_BADGE} Focus · ${riskEmoji(hud.risk_tier)} ${hud.risk_tier} · ${n} downstream`;
    reason = hud.summary;
  } else if (danger) {
    title = `⚠️ Focus · Danger Zone · ${riskEmoji(hud.risk_tier)} ${hud.risk_tier}`;
    reason = danger.reason;
  } else if (downstream) {
    title = `➡️ Focus · ${downstream.hops} hops from change`;
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
