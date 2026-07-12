import * as path from "node:path";
import * as vscode from "vscode";

import { FocusCodeLensProvider } from "./codeLens";
import { auditLocal, FocusCliError, traceFile, workspaceRoot, workspaceRootError } from "./focusCli";
import { FocusGutter } from "./gutter";
import { HudPanel } from "./hudPanel";
import { InlineExplanation } from "./inlineExplanation";
import { watchLensFontSize } from "./lensFont";
import type { FocusHUD } from "./types";

const SOURCE_LANGUAGE_IDS = new Set([
  "python",
  "javascript",
  "javascriptreact",
  "typescript",
  "typescriptreact",
]);

/** Debounce saves so rapid Cmd+S / format-on-save doesn't stack audits. */
const AUTO_AUDIT_DEBOUNCE_MS = 400;

let lastHud: FocusHUD | undefined;
let statusBar: vscode.StatusBarItem;
let lenses: FocusCodeLensProvider;
let gutter: FocusGutter;
let inlineExplanation: InlineExplanation;
let auditInFlight: Promise<void> | undefined;
let autoAuditTimer: ReturnType<typeof setTimeout> | undefined;

export function activate(context: vscode.ExtensionContext): void {
  const extVersion = context.extension.packageJSON.version as string;
  lenses = new FocusCodeLensProvider();
  gutter = new FocusGutter();
  inlineExplanation = new InlineExplanation();
  watchLensFontSize(context);
  context.subscriptions.push({ dispose: () => gutter.dispose() });
  context.subscriptions.push({ dispose: () => inlineExplanation.dispose() });
  context.subscriptions.push({
    dispose: () => {
      if (autoAuditTimer) {
        clearTimeout(autoAuditTimer);
      }
    },
  });
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
    // Focus reads git/disk — refresh after save so rails update in place (no Reload).
    vscode.workspace.onDidSaveTextDocument((document) => {
      scheduleAutoAudit(document, extVersion);
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

function autoAuditOnSaveEnabled(): boolean {
  return vscode.workspace.getConfiguration("focus").get<boolean>("autoAuditOnSave", true);
}

function scheduleAutoAudit(document: vscode.TextDocument, extVersion: string): void {
  if (!autoAuditOnSaveEnabled()) {
    return;
  }
  if (document.uri.scheme !== "file") {
    return;
  }
  if (!SOURCE_LANGUAGE_IDS.has(document.languageId)) {
    return;
  }
  const root = workspaceRoot();
  if (!root) {
    return;
  }
  const rel = path.relative(root, document.uri.fsPath);
  if (!rel || rel.startsWith("..")) {
    return;
  }

  if (autoAuditTimer) {
    clearTimeout(autoAuditTimer);
  }
  autoAuditTimer = setTimeout(() => {
    autoAuditTimer = undefined;
    void runAudit(true, extVersion);
  }, AUTO_AUDIT_DEBOUNCE_MS);
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
  // Serialize audits — overlapping save/audit races leave stale CodeLens.
  if (auditInFlight) {
    await auditInFlight;
  }
  const work = (async () => {
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
  })();
  auditInFlight = work.finally(() => {
    if (auditInFlight === work) {
      auditInFlight = undefined;
    }
  });
  await auditInFlight;
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
