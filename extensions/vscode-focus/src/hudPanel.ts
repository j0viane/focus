import * as vscode from "vscode";

import type { FocusHUD } from "./types";

export class HudPanel {
  public static current: HudPanel | undefined;
  private readonly panel: vscode.WebviewPanel;

  private constructor(panel: vscode.WebviewPanel) {
    this.panel = panel;
    this.panel.onDidDispose(() => {
      if (HudPanel.current === this) {
        HudPanel.current = undefined;
      }
    });
  }

  static show(hud: FocusHUD): void {
    const column = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.Beside;
    if (HudPanel.current) {
      HudPanel.current.panel.reveal(column);
      HudPanel.current.render(hud);
      return;
    }
    const panel = vscode.window.createWebviewPanel(
      "focusHud",
      "Focus HUD",
      column,
      { enableScripts: true, retainContextWhenHidden: true },
    );
    HudPanel.current = new HudPanel(panel);
    HudPanel.current.render(hud);
  }

  private render(hud: FocusHUD): void {
    this.panel.title = `Focus · ${hud.risk_tier}`;
    this.panel.webview.html = buildHtml(hud);
  }
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildHtml(hud: FocusHUD): string {
  const danger = hud.danger_zones
    .map(
      (z) =>
        `<li><code>${escapeHtml(z.path)}</code> <span class="muted">(${z.hops} hops)</span><br/><span class="reason">${escapeHtml(z.reason)}</span></li>`,
    )
    .join("");
  const downstream = hud.downstream
    .map(
      (z) =>
        `<li><code>${escapeHtml(z.path)}</code> <span class="muted">(${z.hops} hops)</span></li>`,
    )
    .join("");
  const mermaidBlock = hud.mermaid
    ? `<pre class="mermaid">${escapeHtml(hud.mermaid)}</pre>`
    : `<p class="muted">No diagram (pass-through / low impact).</p>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src https://cdn.jsdelivr.net 'unsafe-inline';" />
  <style>
    :root { color-scheme: light dark; }
    body { font-family: var(--vscode-font-family); padding: 1.25rem 1.5rem; line-height: 1.45; color: var(--vscode-foreground); }
    h1 { font-size: 1.25rem; margin: 0 0 0.35rem; }
    .tier { font-weight: 700; }
    .tier.CRITICAL, .tier.HIGH { color: #f07178; }
    .tier.MEDIUM { color: #e0af68; }
    .tier.LOW { color: #7dd3c0; }
    .summary { margin: 0.75rem 0 1.25rem; opacity: 0.95; }
    .muted { opacity: 0.65; font-size: 0.9em; }
    .reason { opacity: 0.8; font-size: 0.9em; }
    code { font-family: var(--vscode-editor-font-family); }
    ul { padding-left: 1.2rem; }
    li { margin: 0.35rem 0; }
    h2 { font-size: 1rem; margin: 1.25rem 0 0.5rem; }
    pre.mermaid { background: transparent; }
    .caveat { margin-top: 1.5rem; font-size: 0.85em; opacity: 0.7; }
  </style>
</head>
<body>
  <h1>Focus <span class="tier ${escapeHtml(hud.risk_tier)}">${escapeHtml(hud.risk_tier)}</span></h1>
  <p class="muted">seed: <code>${escapeHtml(hud.seed)}</code> · mode: ${escapeHtml(hud.mode)}</p>
  <p class="summary">${escapeHtml(hud.summary)}</p>
  <h2>Architecture impact</h2>
  ${mermaidBlock}
  <h2>Danger Zones</h2>
  ${danger ? `<ul>${danger}</ul>` : `<p class="muted">(none)</p>`}
  <h2>Downstream</h2>
  ${downstream ? `<ul>${downstream}</ul>` : `<p class="muted">(none)</p>`}
  ${hud.caveat ? `<p class="caveat">${escapeHtml(hud.caveat)}</p>` : ""}
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
    mermaid.initialize({ startOnLoad: true, theme: "dark" });
  </script>
</body>
</html>`;
}
