import { EXPLAIN_PREFIX } from "./icons";
import type { ChangedSymbolInfo, EvidenceItem } from "./types";

/** Readable line width for stacked CodeLens rows (full text, word-wrapped). */
const WRAP_WIDTH = 96;

/** Max evidence bullets in CodeLens hover (ROA — trust cues only). */
const MAX_HOVER_EVIDENCE = 2;

/** Strip markdown backticks for readable editor chrome. */
export function stripMarkdown(text: string): string {
  return text.replace(/`([^`]+)`/g, "$1").replace(/\s+/g, " ").trim();
}

/** Word-wrap plain text — never truncates with an ellipsis. */
export function wrapReadable(text: string, maxLen = WRAP_WIDTH): string[] {
  const plain = stripMarkdown(text);
  if (!plain) {
    return [];
  }
  const words = plain.split(" ");
  const lines: string[] = [];
  let current: string[] = [];
  for (const word of words) {
    const candidate = current.length ? `${current.join(" ")} ${word}` : word;
    if (candidate.length > maxLen && current.length) {
      lines.push(current.join(" "));
      current = [word];
    } else {
      current.push(word);
    }
  }
  if (current.length) {
    lines.push(current.join(" "));
  }
  return lines;
}

/** Stack wrapped lines under a prefix (first line carries the prefix). */
export function stackedLensTitle(prefix: string, text: string, maxLen = WRAP_WIDTH): string {
  const lines = wrapReadable(text, maxLen);
  if (!lines.length) {
    return prefix;
  }
  return [prefix + " " + lines[0], ...lines.slice(1)].join("\n");
}

export function summaryLensTitle(text: string): string {
  return wrapReadable(text).join("\n");
}

export function explanationLensTitle(text: string): string {
  const lines = wrapReadable(text);
  if (!lines.length) {
    return EXPLAIN_PREFIX;
  }
  return [EXPLAIN_PREFIX + " " + lines[0], ...lines.slice(1)].join("\n");
}

/**
 * CodeLens tooltip — answers "why trust this caption?" only.
 *
 * Does not restate implication / purpose (those live on the rail and ℹ️).
 * Graph map belongs in the HUD panel.
 */
export function evidenceMarkdown(sym: ChangedSymbolInfo, _purpose?: string): string {
  const parts: string[] = [];
  const evidence = (sym.evidence ?? []).slice(0, MAX_HOVER_EVIDENCE);
  if (evidence.length) {
    parts.push("**Why trust this**");
    parts.push(evidence.map((item) => formatEvidenceBullet(item)).join("\n\n"));
  } else {
    parts.push("**Why trust this**\n\nNo cite list on this symbol — open the HUD for graph context.");
  }
  parts.push("Open Focus HUD for the full map");
  return parts.filter(Boolean).join("\n\n");
}

function formatEvidenceBullet(item: EvidenceItem): string {
  const label = item.confidence === "proven" ? "Proven" : "Heuristic";
  return `**${label}** · ${item.fact}`;
}
