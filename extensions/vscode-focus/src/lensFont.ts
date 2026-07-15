import * as vscode from "vscode";

/**
 * Focus rails are CodeLens. VS Code splits the switch:
 * - `editor.codeLens` → normal file tabs
 * - `diffEditor.codeLens` → SCM / side-by-side diffs
 * Enabling only the diff default left the open file blank — turn both on for this workspace.
 */
export function ensureCodeLensSurfaces(): void {
  const editorCfg = vscode.workspace.getConfiguration("editor");
  if (editorCfg.get<boolean>("codeLens") !== true) {
    void editorCfg.update("codeLens", true, vscode.ConfigurationTarget.Workspace);
  }
  const diffCfg = vscode.workspace.getConfiguration("diffEditor");
  if (diffCfg.get<boolean>("codeLens") !== true) {
    void diffCfg.update("codeLens", true, vscode.ConfigurationTarget.Workspace);
  }
}

/**
 * CodeLens font size is owned by VS Code (`editor.codeLensFontSize`), not per-lens styling.
 * When `focus.lensFontSize` is set, sync that workspace setting so Focus rows are readable.
 */
export function applyLensFontSize(): void {
  const focusCfg = vscode.workspace.getConfiguration("focus");
  const requested = focusCfg.get<number>("lensFontSize", 0);
  if (requested === 0) {
    return;
  }

  const editorCfg = vscode.workspace.getConfiguration("editor");
  const editorSize = editorCfg.get<number>("fontSize", 14);
  const target = requested < 0 ? editorSize : requested;

  if (editorCfg.get<number>("codeLensFontSize") === target) {
    return;
  }

  void editorCfg.update("codeLensFontSize", target, vscode.ConfigurationTarget.Workspace);
}

export function watchLensFontSize(context: vscode.ExtensionContext): void {
  ensureCodeLensSurfaces();
  applyLensFontSize();
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("focus.lensFontSize")) {
        applyLensFontSize();
      }
    }),
  );
}
