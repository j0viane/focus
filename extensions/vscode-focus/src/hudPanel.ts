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
  const changed = hud.changed_symbols
    .map(
      (s) =>
        `<li><code>${escapeHtml(s.path)}</code> → <strong>${escapeHtml(s.name)}</strong> ` +
        `<span class="muted">(${escapeHtml(s.kind)}, line ${s.line})</span></li>`,
    )
    .join("");
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
    body {
      font-family: var(--vscode-font-family);
      padding: 1.25rem 1.5rem;
      line-height: 1.55;
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
    }
    h1 { font-size: 1.35rem; margin: 0 0 0.5rem; font-weight: 600; }
    h2 { font-size: 1.05rem; margin: 1.5rem 0 0.6rem; font-weight: 600; }
    h2:first-of-type { margin-top: 1rem; }
    .tier { font-weight: 700; }
    .tier.CRITICAL, .tier.HIGH { color: #f07178; }
    .tier.MEDIUM { color: #e0af68; }
    .tier.LOW { color: #7dd3c0; }
    .summary { margin: 0.75rem 0 1rem; line-height: 1.5; }
    .meta { color: var(--vscode-descriptionForeground); font-size: 0.9em; margin-bottom: 0.5rem; }
    .muted { color: var(--vscode-descriptionForeground); font-size: 0.92em; }
    .reason { color: var(--vscode-foreground); font-size: 0.95em; }
    code {
      font-family: var(--vscode-editor-font-family);
      background: var(--vscode-textCodeBlock-background, rgba(127,127,127,0.15));
      padding: 0.1em 0.35em;
      border-radius: 3px;
    }
    ul { padding-left: 1.25rem; margin: 0.4rem 0 0.8rem; }
    li { margin: 0.45rem 0; }
    li strong { color: var(--vscode-textLink-foreground, #79c0ff); font-weight: 600; }
    pre.mermaid { background: transparent; margin: 0.5rem 0; }
    .caveat { margin-top: 1.5rem; font-size: 0.9em; color: var(--vscode-descriptionForeground); }
  </style>
</head>
<body>
  <h1>Focus <span class="tier ${escapeHtml(hud.risk_tier)}">${escapeHtml(hud.risk_tier)}</span></h1>
  <p class="meta">seed: <code>${escapeHtml(hud.seed)}</code> · mode: ${escapeHtml(hud.mode)}</p>
  <p class="summary">${escapeHtml(hud.summary)}</p>
  ${changed ? `<h2>Your changes</h2><ul>${changed}</ul>` : ""}
  <h2>Architecture impact</h2>
  ${mermaidBlock}
  <h2>Danger Zones</h2>
  ${danger ? `<ul>${danger}</ul>` : `<p class="muted">(none)</p>`}
  <h2>Downstream</h2>
  ${downstream ? `<ul>${downstream}</ul>` : `<p class="muted">(none)</p>`}
  ${hud.caveat ? `<p class="caveat">${escapeHtml(hud.caveat)}</p>` : ""}
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
    mermaid.initialize({ startOnLoad: true, theme: "base", themeVariables: {
      darkMode: "true",
      background: "transparent",
      primaryTextColor: "#e6edf3",
      lineColor: "#8b949e",
      primaryColor: "#30363d",
      primaryBorderColor: "#8b949e",
    }});
  </script>
</body>
</html>`;
}
