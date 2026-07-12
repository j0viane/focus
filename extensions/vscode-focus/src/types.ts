/** FocusHUD JSON from `focus … --format json` (FocusHUD pydantic model). */

export type RiskTier = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type HudMode = "full" | "pass_through" | "error";

export interface ImpactNode {
  path: string;
  hops: number;
  reason: string;
}

export interface ChangedSymbolInfo {
  path: string;
  name: string;
  kind: "function" | "class";
  line: number;
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
  caveat: string | null;
}
