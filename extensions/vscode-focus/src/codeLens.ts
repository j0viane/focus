import * as path from "node:path";
import * as vscode from "vscode";

import {
  definitionLine,
  editorLine,
  hunkDetailsForSymbol,
  lensRange,
  preferCodeLine,
} from "./symbolLayout";
import { FOCUS_BADGE, riskEmoji } from "./icons";
import { evidenceMarkdown, explanationLensTitle, summaryLensTitle } from "./explainText";
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
    // Fire twice: some editors keep stale CodeLens titles until a second invalidate.
    this._onDidChange.fire();
    queueMicrotask(() => this._onDidChange.fire());
  }

  provideCodeLenses(
    document: vscode.TextDocument,
  ): vscode.ProviderResult<vscode.CodeLens[]> {
    if (!this.hud || !this.root) {
      return [];
    }
    // Modified (working-tree) side is `file:`; skip git/virtual base panes in SCM diffs.
    if (document.uri.scheme !== "file") {
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
  const lenses: vscode.CodeLens[] = [];
  const implication = sym.implication || "";
  const railLine = preferCodeLine(document, defLine);

  // Risk rail above `def` — quiet when implication is empty (LOW, or ROA gaps).
  // Captions (ℹ️) still show below whenever we have detail — including LOW.
  if (implication) {
    lenses.push(
      new vscode.CodeLens(lensRange(document, railLine), {
        title: summaryLensTitle(implication),
        command: "focus.showEvidence",
        arguments: [document.uri, railLine, evidenceMarkdown(sym)],
        tooltip: "Click for why to trust this · or hover the highlighted code",
      }),
    );
  }

  let captionCount = 0;
  if (inlineExplanationsEnabled()) {
    for (const hunk of hunkDetailsForSymbol(sym)) {
      const raw = editorLine(hunk.line);
      if (raw >= document.lineCount || !hunk.detail) {
        continue;
      }
      const blankOnly = isBlankLineDetail(hunk.detail);
      // Blank-only edits stay on the blank; other edits skip blank anchors.
      const line = blankOnly
        ? raw
        : preferCodeLine(document, raw, hunk.changed_lines ?? []);
      const trust = blankOnly
        ? "Whitespace only — no behavior change."
        : evidenceMarkdown(sym, hunk.detail);
      lenses.push(
        new vscode.CodeLens(lensRange(document, line), {
          title: explanationLensTitle(hunk.detail),
          command: "focus.showEvidence",
          arguments: [document.uri, line, trust],
          tooltip: blankOnly
            ? "Whitespace-only edit"
            : "Click for why to trust this · or hover the highlighted code",
        }),
      );
      captionCount += 1;
    }

    // Guarantee an ℹ️ when HUD has symbol.detail but no hunk anchors landed
    // (common on LOW: quiet rail, still narrate the edit).
    const fallbackDetail = (sym.detail || "").trim();
    if (captionCount === 0 && fallbackDetail) {
      lenses.push(
        new vscode.CodeLens(lensRange(document, railLine), {
          title: explanationLensTitle(fallbackDetail),
          command: "focus.showEvidence",
          arguments: [document.uri, railLine, evidenceMarkdown(sym, fallbackDetail)],
          tooltip: "Click for why to trust this · or hover the highlighted code",
        }),
      );
      captionCount += 1;
    }
  }

  // Last-resort badge when we have neither rail nor caption — skip on LOW (ROA).
  if (!lenses.length && hud.risk_tier !== "LOW") {
    const n = hud.downstream.length;
    const badge = `${FOCUS_BADGE} Focus · ${sym.name} · ${riskEmoji(hud.risk_tier as RiskTier)} ${hud.risk_tier} · ${n} downstream`;
    lenses.push(
      new vscode.CodeLens(lensRange(document, railLine), {
        title: badge,
        command: "focus.showEvidence",
        arguments: [
          document.uri,
          railLine,
          evidenceMarkdown(sym) || sym.explanation || `${sym.kind} ${sym.name}`,
        ],
        tooltip: "Click for why to trust this · or hover the highlighted code",
      }),
    );
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
  const line = preferCodeLine(
    document,
    editorLine(note.line),
    note.changed_lines ?? [],
  );
  if (line >= document.lineCount) {
    return [];
  }
  return [
    new vscode.CodeLens(lensRange(document, line), {
      title: explanationLensTitle(note.detail),
      command: "focus.showEvidence",
      arguments: [document.uri, line, note.detail],
      tooltip: "Click for detail · or hover the highlighted code",
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

function isBlankLineDetail(detail: string): boolean {
  return /^added (a|\d+) blank lines?\.?$/i.test(detail.trim());
}
