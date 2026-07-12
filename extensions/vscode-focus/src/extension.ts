import * as vscode from "vscode";

import { FocusCodeLensProvider } from "./codeLens";
import { auditLocal, FocusCliError, traceFile, workspaceRoot, workspaceRootError } from "./focusCli";
import { FocusGutter } from "./gutter";
import { HudPanel } from "./hudPanel";
import { InlineExplanation } from "./inlineExplanation";
import { watchLensFontSize } from "./lensFont";
import type { FocusHUD } from "./types";

let lastHud: FocusHUD | undefined;
let statusBar: vscode.StatusBarItem;
let lenses: FocusCodeLensProvider;
let gutter: FocusGutter;
let inlineExplanation: InlineExplanation;

export function activate(context: vscode.ExtensionContext): void {
  const extVersion = context.extension.packageJSON.version as string;
  lenses = new FocusCodeLensProvider();
  gutter = new FocusGutter();
  inlineExplanation = new InlineExplanation();
  watchLensFontSize(context);
  context.subscriptions.push({ dispose: () => gutter.dispose() });
  context.subscriptions.push({ dispose: () => inlineExplanation.dispose() });
  const hintLanguages = [
    { language: "python" },
    { language: "javascript" },
    { language: "javascriptreact" },
    { language: "typescript" },
    { language: "typescriptreact" },
  ];

  context.subscriptions.push(
    vscode.languages.registerCodeLensProvider(hintLanguages, lenses),
    vscode.languages.registerHoverProvider(
      hintLanguages,
      {
        provideHover: (doc, pos) => inlineExplanation.provideHover(doc, pos),
      },
    ),
  );

  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.command = "focus.showHud";
  statusBar.tooltip = "Focus HUD";
  statusBar.text = "Focus";
  statusBar.show();
  context.subscriptions.push(statusBar);

  context.subscriptions.push(
    vscode.commands.registerCommand("focus.auditLocal", () => runAudit(false, extVersion)),
    vscode.commands.registerCommand("focus.traceCurrentFile", () => runTrace(extVersion)),
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
    vscode.commands.registerCommand("focus.noop", () => undefined),
    vscode.commands.registerCommand("focus.refresh", () => runAudit(true, extVersion)),
  );

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        gutter.apply(editor);
        inlineExplanation.apply(editor);
      }
    }),
  );

  whenWorkspaceReady(context, (version) => runAudit(true, version));
}

function whenWorkspaceReady(
  context: vscode.ExtensionContext,
  fn: (extVersion: string) => void | Promise<void>,
): void {
  const extVersion = context.extension.packageJSON.version as string;
  if (vscode.workspace.workspaceFolders?.length) {
    void fn(extVersion);
    return;
  }
  const sub = vscode.workspace.onDidChangeWorkspaceFolders(() => {
    if (vscode.workspace.workspaceFolders?.length) {
      sub.dispose();
      void fn(extVersion);
    }
  });
  context.subscriptions.push(sub);
}

export function deactivate(): void {
  // noop
}

function setHud(hud: FocusHUD, root: string, extVersion: string): void {
  lastHud = hud;
  lenses.refresh(hud, root);
  gutter.refresh(hud, root);
  inlineExplanation.refresh(hud, root);
  statusBar.text = `Focus · ${hud.risk_tier}`;
  statusBar.tooltip = `${hud.summary}\n\nFocus extension v${extVersion}`;
}

async function runAudit(quiet = false, extVersion = "dev"): Promise<void> {
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
    setHud(hud, root, extVersion);
    if (!quiet) {
      HudPanel.show(hud);
    }
  } catch (err) {
    reportError(err, quiet);
  }
}

async function runTrace(extVersion = "dev"): Promise<void> {
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
    setHud(hud, root, extVersion);
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
