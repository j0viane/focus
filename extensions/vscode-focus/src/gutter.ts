import * as path from "node:path";
import * as vscode from "vscode";

import type { FocusHUD, ImpactNode, RiskTier } from "./types";

const TIER_RGBA: Record<RiskTier, string> = {
  CRITICAL: "rgba(240, 113, 120, 0.35)",
  HIGH: "rgba(240, 113, 120, 0.28)",
  MEDIUM: "rgba(224, 175, 104, 0.28)",
  LOW: "rgba(125, 211, 192, 0.22)",
};

const TIER_RULER: Record<RiskTier, string> = {
  CRITICAL: "#f07178",
  HIGH: "#f07178",
  MEDIUM: "#e0af68",
  LOW: "#7dd3c0",
};

const DOWNSTREAM_RGBA = "rgba(224, 175, 104, 0.18)";
const DANGER_RGBA = "rgba(240, 113, 120, 0.22)";

export class FocusGutter {
  private hud: FocusHUD | undefined;
  private root: string | undefined;
  private readonly changedStyle: vscode.TextEditorDecorationType;
  private readonly dangerStyle: vscode.TextEditorDecorationType;
  private readonly downstreamStyle: vscode.TextEditorDecorationType;

  constructor() {
    this.changedStyle = vscode.window.createTextEditorDecorationType({
      isWholeLine: true,
      backgroundColor: TIER_RGBA.HIGH,
      overviewRulerColor: TIER_RULER.HIGH,
      overviewRulerLane: vscode.OverviewRulerLane.Left,
    });
    this.dangerStyle = vscode.window.createTextEditorDecorationType({
      isWholeLine: true,
      overviewRulerColor: TIER_RULER.HIGH,
      overviewRulerLane: vscode.OverviewRulerLane.Center,
      backgroundColor: DANGER_RGBA,
    });
    this.downstreamStyle = vscode.window.createTextEditorDecorationType({
      isWholeLine: true,
      overviewRulerColor: TIER_RULER.MEDIUM,
      overviewRulerLane: vscode.OverviewRulerLane.Right,
      backgroundColor: DOWNSTREAM_RGBA,
    });
  }

  dispose(): void {
    this.changedStyle.dispose();
    this.dangerStyle.dispose();
    this.downstreamStyle.dispose();
  }

  refresh(hud: FocusHUD | undefined, root: string | undefined): void {
    this.hud = hud;
    this.root = root;
    this.applyAll();
  }

  applyAll(): void {
    for (const editor of vscode.window.visibleTextEditors) {
      this.apply(editor);
    }
  }

  apply(editor: vscode.TextEditor): void {
    if (!this.hud || !this.root || !gutterEnabled()) {
      editor.setDecorations(this.changedStyle, []);
      editor.setDecorations(this.dangerStyle, []);
      editor.setDecorations(this.downstreamStyle, []);
      return;
    }

    const rel = relPath(this.root, editor.document.uri.fsPath);
    if (!rel) {
      return;
    }

    const changedRanges = changedSymbolRanges(this.hud, rel, editor.document.lineCount);
    editor.setDecorations(this.changedStyle, changedRanges);

    const danger = lookupNode(this.hud.danger_zones, rel);
    const downstream = lookupNode(this.hud.downstream, rel);
    if (danger && !changedRanges.length) {
      editor.setDecorations(this.dangerStyle, [lineRange(0)]);
    } else {
      editor.setDecorations(this.dangerStyle, []);
    }
    if (downstream && !danger && !changedRanges.length) {
      editor.setDecorations(this.downstreamStyle, [lineRange(0)]);
    } else {
      editor.setDecorations(this.downstreamStyle, []);
    }
  }
}

function gutterEnabled(): boolean {
  return vscode.workspace.getConfiguration("focus").get<boolean>("gutter", true);
}

function relPath(root: string, fsPath: string): string | undefined {
  const rel = path.relative(root, fsPath).split(path.sep).join("/");
  if (!rel || rel.startsWith("..")) {
    return undefined;
  }
  return rel;
}

function lineRange(line: number): vscode.DecorationOptions {
  return { range: new vscode.Range(line, 0, line, 0) };
}

function changedSymbolRanges(
  hud: FocusHUD,
  rel: string,
  lineCount: number,
): vscode.DecorationOptions[] {
  return hud.changed_symbols
    .filter((s) => s.path === rel)
    .map((s) => {
      const line = Math.max(0, Math.min(s.line - 1, lineCount - 1));
      return lineRange(line);
    });
}

function lookupNode(nodes: ImpactNode[], rel: string): ImpactNode | undefined {
  return nodes.find((n) => n.path === rel);
}
