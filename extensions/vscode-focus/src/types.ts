/** FocusHUD JSON from `focus … --format json` (FocusHUD pydantic model). */

export type RiskTier = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type HudMode = "full" | "pass_through" | "error";
export type Confidence = "proven" | "heuristic";

/** The import statement that proves one blast-radius edge (from the parser). */
export interface ImportEvidence {
  /** Repo-relative posix path of the file containing the import line. */
  path: string;
  /** 1-based line of the import statement. */
  line: number;
  /** Imported module string exactly as written. */
  module: string;
}

export interface ImpactNode {
  path: string;
  hops: number;
  reason: string;
  /** Import line(s) proving this edge; empty for transitive (hop >= 2) nodes. */
  import_evidence?: ImportEvidence[];
}

export interface HunkDetail {
  line: number;
  changed_lines?: number[];
  detail: string;
}

export interface EvidenceItem {
  confidence: Confidence;
  kind: string;
  location: string;
  fact: string;
}

export interface ChangedSymbolInfo {
  path: string;
  name: string;
  kind: "function" | "class";
  line: number;
  changed_lines?: number[];
  summary?: string;
  detail?: string;
  explanation?: string;
  /** Risk rail: "{emoji} {RISK} — {who} — {what goes wrong}". Empty when quiet. */
  implication?: string;
  hunk_details?: HunkDetail[];
  evidence?: EvidenceItem[];
}

/** Inline explainer for diff hunks outside any changed symbol body. */
export interface LineExplanation {
  path: string;
  line: number;
  changed_lines?: number[];
  detail: string;
}

export interface FocusHUD {
  mode: HudMode;
  seed: string;
  summary: string;
  risk_tier: RiskTier;
  mermaid: string | null;
  danger_zones: ImpactNode[];
  downstream: ImpactNode[];
  isolated: string[];
  changed_symbols: ChangedSymbolInfo[];
  line_explanations?: LineExplanation[];
  caveat: string | null;
}
