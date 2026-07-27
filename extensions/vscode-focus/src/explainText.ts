import { EXPLAIN_PREFIX } from "./icons";
import type { ChangedSymbolInfo, EvidenceItem } from "./types";

/** Max evidence bullets in CodeLens hover (ROA — trust cues only). */
const MAX_HOVER_EVIDENCE = 2;

/** Strip markdown backticks for readable editor chrome. */
export function stripMarkdown(text: string): string {
  return text.replace(/`([^`]+)`/g, "$1").replace(/\s+/g, " ").trim();
}

/**
 * Single CodeLens title for an ℹ️ caption.
 *
 * Do not split into multiple lenses on the same line — Cursor joins those with
 * ` | `, which reads as pipes in the middle of the sentence.
 */
export function explanationLensTitle(text: string): string {
  const plain = stripMarkdown(text);
  if (!plain) {
    return EXPLAIN_PREFIX;
  }
  return `${EXPLAIN_PREFIX} ${plain}`;
}

/**
 * CodeLens tooltip — answers "why trust this caption?" only.
 *
 * Does not restate implication / purpose (those live in the HUD and ℹ️).
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
