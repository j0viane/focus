import type { RiskTier } from "./types";

/** Risk tier dots — same language as the HUD / PR comment. */
export function riskEmoji(tier: RiskTier): string {
  switch (tier) {
    case "CRITICAL":
      return "🔴";
    case "HIGH":
      return "🟠";
    case "MEDIUM":
      return "🟡";
    case "LOW":
      return "🟢";
  }
}

export const FOCUS_BADGE = "🎯";

/** Info mark — clear “explanation” meaning; readable on light themes. */
export const EXPLAIN_PREFIX = "ℹ️";
