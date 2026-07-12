import * as path from "node:path";
import * as vscode from "vscode";

import { editorLine, highlightLines } from "./symbolLayout";
import type { ChangedSymbolInfo, FocusHUD, ImpactNode, LineExplanation, RiskTier } from "./types";

const TIER_BORDER: Record<RiskTier, string> = {
  CRITICAL: "#f07178",
  HIGH: "#f07178",
  MEDIUM: "#e0af68",
  LOW: "#7dd3c0",
};

const TIER_GLOW: Record<RiskTier, string> = {
  CRITICAL: "rgba(240, 113, 120, 0.12)",
  HIGH: "rgba(240, 113, 120, 0.10)",
  MEDIUM: "rgba(224, 175, 104, 0.10)",
  LOW: "rgba(125, 211, 192, 0.10)",
};

const DOWNSTREAM_RGBA = "rgba(224, 175, 104, 0.12)";
const DANGER_RGBA = "rgba(240, 113, 120, 0.14)";

export class FocusGutter {
  private hud: FocusHUD | undefined;
  private root: string | undefined;
  private readonly changedStyles: Record<RiskTier, vscode.TextEditorDecorationType>;
  private readonly dangerStyle: vscode.TextEditorDecorationType;
  private readonly downstreamStyle: vscode.TextEditorDecorationType;

  constructor() {
    this.changedStyles = {
      CRITICAL: makeChangedStyle(TIER_BORDER.CRITICAL, TIER_GLOW.CRITICAL),
      HIGH: makeChangedStyle(TIER_BORDER.HIGH, TIER_GLOW.HIGH),
      MEDIUM: makeChangedStyle(TIER_BORDER.MEDIUM, TIER_GLOW.MEDIUM),
      LOW: makeChangedStyle(TIER_BORDER.LOW, TIER_GLOW.LOW),
    };
    this.dangerStyle = vscode.window.createTextEditorDecorationType({
      isWholeLine: true,
      overviewRulerColor: TIER_BORDER.HIGH,
      overviewRulerLane: vscode.OverviewRulerLane.Center,
      backgroundColor: DANGER_RGBA,
    });
    this.downstreamStyle = vscode.window.createTextEditorDecorationType({
      isWholeLine: true,
      overviewRulerColor: TIER_BORDER.MEDIUM,
      overviewRulerLane: vscode.OverviewRulerLane.Right,
      backgroundColor: DOWNSTREAM_RGBA,
    });
  }

  dispose(): void {
    for (const style of Object.values(this.changedStyles)) {
      style.dispose();
    }
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
      this.clear(editor);
      return;
    }

    const rel = relPath(this.root, editor.document.uri.fsPath);
    if (!rel) {
      return;
    }

    const symbols = this.hud.changed_symbols.filter((s) => s.path === rel);
    const tier = this.hud.risk_tier;
    const changedStyle = this.changedStyles[tier];

    const changedRanges = changedSymbolRanges(symbols, editor.document.lineCount);
    const orphanRanges = orphanLineRanges(
      this.hud.line_explanations ?? [],
      rel,
      editor.document.lineCount,
    );
    editor.setDecorations(changedStyle, [...changedRanges, ...orphanRanges]);
    for (const [risk, style] of Object.entries(this.changedStyles) as [RiskTier, vscode.TextEditorDecorationType][]) {
      if (risk !== tier) {
        editor.setDecorations(style, []);
      }
    }

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

  private clear(editor: vscode.TextEditor): void {
    for (const style of Object.values(this.changedStyles)) {
      editor.setDecorations(style, []);
    }
    editor.setDecorations(this.dangerStyle, []);
    editor.setDecorations(this.downstreamStyle, []);
  }
}

function makeChangedStyle(
  border: string,
  glow: string,
): vscode.TextEditorDecorationType {
  return vscode.window.createTextEditorDecorationType({
    isWholeLine: true,
    backgroundColor: glow,
    overviewRulerColor: border,
    overviewRulerLane: vscode.OverviewRulerLane.Left,
  });
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
  symbols: ChangedSymbolInfo[],
  lineCount: number,
): vscode.DecorationOptions[] {
  const seen = new Set<number>();
  const ranges: vscode.DecorationOptions[] = [];
  for (const sym of symbols) {
    for (const line of highlightLines(sym)) {
      if (line < lineCount && !seen.has(line)) {
        seen.add(line);
        ranges.push(lineRange(line));
      }
    }
  }
  return ranges;
}

function orphanLineRanges(
  notes: LineExplanation[],
  rel: string,
  lineCount: number,
): vscode.DecorationOptions[] {
  const seen = new Set<number>();
  const ranges: vscode.DecorationOptions[] = [];
  for (const note of notes) {
    if (note.path !== rel) {
      continue;
    }
    const lines = note.changed_lines?.length ? note.changed_lines : [note.line];
    for (const oneBased of lines) {
      const line = editorLine(oneBased);
      if (line < lineCount && !seen.has(line)) {
        seen.add(line);
        ranges.push(lineRange(line));
      }
    }
  }
  return ranges;
}

function lookupNode(nodes: ImpactNode[], rel: string): ImpactNode | undefined {
  return nodes.find((n) => n.path === rel);
}
