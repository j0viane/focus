import * as vscode from "vscode";

import type { ChangedSymbolInfo, HunkDetail } from "./types";

/** Max edit blocks per symbol that get a 💡 row (avoids spam on huge diffs). */
const MAX_DETAIL_ANCHORS = 6;

/** 0-based editor line for a changed symbol definition. */
export function definitionLine(sym: ChangedSymbolInfo): number {
  return Math.max(0, sym.line - 1);
}

/** 0-based editor line from Focus's 1-based line numbers. */
export function editorLine(oneBased: number): number {
  return Math.max(0, oneBased - 1);
}

/** Group sorted 1-based lines into contiguous runs. */
function contiguousRuns(lines: number[]): number[][] {
  if (!lines.length) {
    return [];
  }
  const runs: number[][] = [[lines[0]]];
  for (let i = 1; i < lines.length; i++) {
    if (lines[i] === lines[i - 1] + 1) {
      runs[runs.length - 1].push(lines[i]);
    } else {
      runs.push([lines[i]]);
    }
  }
  return runs;
}

/**
 * 0-based lines for 💡 detail rows — one per contiguous edit block inside the symbol.
 */
export function explanationAnchorLines(sym: ChangedSymbolInfo): number[] {
  const changed = sym.changed_lines ?? [];
  const bodyLines = changed.filter((line) => line !== sym.line).sort((a, b) => a - b);
  if (bodyLines.length > 0) {
    const anchors = contiguousRuns(bodyLines)
      .slice(0, MAX_DETAIL_ANCHORS)
      .map((run) => editorLine(run[0]));
    return [...new Set(anchors)];
  }
  if (changed.length > 0) {
    const anchor = changed[0] === sym.line ? sym.line + 1 : changed[0];
    return [editorLine(anchor)];
  }
  return [editorLine(sym.line + 1)];
}

/** 0-based lines to tint — every git-touched line for this symbol. */
export function highlightLines(sym: ChangedSymbolInfo): number[] {
  const changed = sym.changed_lines ?? [];
  if (!changed.length) {
    return [definitionLine(sym)];
  }
  return [...new Set(changed.map(editorLine))].sort((a, b) => a - b);
}

export function lineInSymbol(sym: ChangedSymbolInfo, position: vscode.Position): boolean {
  return (
    position.line === definitionLine(sym) || highlightLines(sym).includes(position.line)
  );
}

/** Hunk-scoped details from the HUD, or one fallback row per anchor line. */
export function hunkDetailsForSymbol(sym: ChangedSymbolInfo): HunkDetail[] {
  if (sym.hunk_details?.length) {
    return sym.hunk_details.slice(0, MAX_DETAIL_ANCHORS);
  }
  const detail = sym.detail ?? sym.explanation ?? "";
  if (!detail) {
    return [];
  }
  return explanationAnchorLines(sym).map((line) => ({
    line: line + 1,
    detail,
  }));
}

export function hunkDetailAtLine(
  sym: ChangedSymbolInfo,
  oneBasedLine: number,
): HunkDetail | undefined {
  return hunkDetailsForSymbol(sym).find((hunk) => {
    const touched = hunk.changed_lines?.length ? hunk.changed_lines : [hunk.line];
    return touched.includes(oneBasedLine);
  });
}
