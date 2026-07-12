import * as vscode from "vscode";

import { FocusCodeLensProvider } from "./codeLens";
import { auditLocal, FocusCliError, traceFile, workspaceRoot, workspaceRootError } from "./focusCli";
import { FocusGutter } from "./gutter";
import { HudPanel } from "./hudPanel";
import type { FocusHUD } from "./types";

let lastHud: FocusHUD | undefined;
let statusBar: vscode.StatusBarItem;
let lenses: FocusCodeLensProvider;
let gutter: FocusGutter;

export function activate(context: vscode.ExtensionContext): void {
  lenses = new FocusCodeLensProvider();
  gutter = new FocusGutter();
  context.subscriptions.push({ dispose: () => gutter.dispose() });
  context.subscriptions.push(
    vscode.languages.registerCodeLensProvider(
      [
        { language: "python" },
        { language: "javascript" },
        { language: "javascriptreact" },
        { language: "typescript" },
        { language: "typescriptreact" },
      ],
      lenses,
    ),
  );

  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.command = "focus.showHud";
  statusBar.tooltip = "Focus HUD";
  statusBar.text = "Focus";
  statusBar.show();
  context.subscriptions.push(statusBar);

  context.subscriptions.push(
    vscode.commands.registerCommand("focus.auditLocal", () => runAudit()),
    vscode.commands.registerCommand("focus.traceCurrentFile", () => runTrace()),
    vscode.commands.registerCommand("focus.showHud", () => {
      if (!lastHud) {
        void vscode.window.showInformationMessage(
          "No Focus HUD yet — run Audit Local Changes or Trace Current File.",
        );
        return;
      }
      HudPanel.show(lastHud);
    }),
    vscode.commands.registerCommand("focus.showWhy", (reason?: string) => {
      if (reason) {
        void vscode.window.showInformationMessage(`Focus: ${reason}`, "Open HUD").then((pick) => {
          if (pick === "Open HUD" && lastHud) {
            HudPanel.show(lastHud);
          }
        });
        return;
      }
      if (lastHud) {
        HudPanel.show(lastHud);
      }
    }),
    vscode.commands.registerCommand("focus.refresh", () => runAudit(true)),
  );

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        gutter.apply(editor);
      }
    }),
  );

  whenWorkspaceReady(context, () => runAudit(true));
}

function whenWorkspaceReady(
  context: vscode.ExtensionContext,
  fn: () => void | Promise<void>,
): void {
  if (vscode.workspace.workspaceFolders?.length) {
    void fn();
    return;
  }
  const sub = vscode.workspace.onDidChangeWorkspaceFolders(() => {
    if (vscode.workspace.workspaceFolders?.length) {
      sub.dispose();
      void fn();
    }
  });
  context.subscriptions.push(sub);
}

export function deactivate(): void {
  // noop
}

function setHud(hud: FocusHUD, root: string): void {
  lastHud = hud;
  lenses.refresh(hud, root);
  gutter.refresh(hud, root);
  statusBar.text = `Focus · ${hud.risk_tier}`;
  statusBar.tooltip = hud.summary;
}

async function runAudit(quiet = false): Promise<void> {
  const root = workspaceRoot();
  if (!root) {
    if (!quiet) {
      void vscode.window.showWarningMessage(workspaceRootError());
    }
    return;
  }
  try {
    const hud = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Window,
        title: "Focus: auditing local changes…",
      },
      () => auditLocal(root),
    );
    setHud(hud, root);
    if (!quiet) {
      HudPanel.show(hud);
    }
  } catch (err) {
    reportError(err, quiet);
  }
}

async function runTrace(): Promise<void> {
  const root = workspaceRoot();
  const editor = vscode.window.activeTextEditor;
  if (!root || !editor) {
    void vscode.window.showWarningMessage("Focus: open a source file in a folder workspace.");
    return;
  }
  try {
    const hud = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Window,
        title: "Focus: tracing file…",
      },
      () => traceFile(root, editor.document.uri.fsPath),
    );
    setHud(hud, root);
    HudPanel.show(hud);
  } catch (err) {
    reportError(err, false);
  }
}

function reportError(err: unknown, quiet: boolean): void {
  const message = err instanceof FocusCliError ? err.message : String(err);
  if (quiet) {
    statusBar.text = "Focus · error";
    statusBar.tooltip = message;
    return;
  }
  void vscode.window.showErrorMessage(`Focus: ${message}`);
}
