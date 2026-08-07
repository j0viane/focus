import * as path from "node:path";
import * as fs from "node:fs";
import * as os from "node:os";
import * as vscode from "vscode";

import { FocusCodeLensProvider } from "./codeLens";
import { editorIsDiffPane } from "./diffEditor";
import { auditLocal, FocusCliError, traceFile, workspaceRoot, workspaceRootError } from "./focusCli";
import { FocusGutter } from "./gutter";
import { HudPanel } from "./hudPanel";
import { InlineExplanation } from "./inlineExplanation";
import { watchLensFontSize } from "./lensFont";
import type { FocusHUD, ImportEvidence } from "./types";

const SOURCE_LANGUAGE_IDS = new Set([
  "python",
  "javascript",
  "javascriptreact",
  "typescript",
  "typescriptreact",
]);

/** Debounce saves so rapid Cmd+S / format-on-save doesn't stack audits. */
const AUTO_AUDIT_DEBOUNCE_MS = 400;
/** Debounce quiet audit when opening SCM diffs without an existing HUD. */
const DIFF_AUDIT_DEBOUNCE_MS = 500;
/** Debounce live buffer overlay audits while typing. */
const LIVE_OVERLAY_DEBOUNCE_MS = 400;
/** Cap dirty files sent in one overlay payload. */
const MAX_OVERLAY_FILES = 3;

let lastHud: FocusHUD | undefined;
let statusBar: vscode.StatusBarItem;
let lenses: FocusCodeLensProvider;
let gutter: FocusGutter;
let inlineExplanation: InlineExplanation;
let auditInFlight: Promise<void> | undefined;
/** Bumped to drop stale background LLM enrich results after a newer audit. */
let llmEnrichGeneration = 0;
let autoAuditTimer: ReturnType<typeof setTimeout> | undefined;
let diffAuditTimer: ReturnType<typeof setTimeout> | undefined;
let liveOverlayTimer: ReturnType<typeof setTimeout> | undefined;

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
      if (diffAuditTimer) {
        clearTimeout(diffAuditTimer);
      }
      if (liveOverlayTimer) {
        clearTimeout(liveOverlayTimer);
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
    // CodeLens title tooltips use native HTML title — flaky on macOS (often once). Click is reliable.
    vscode.commands.registerCommand(
      "focus.showEvidence",
      async (uri?: vscode.Uri, line?: number, markdown?: string) => {
        if (uri && typeof line === "number") {
          const doc = await vscode.workspace.openTextDocument(uri);
          const editor = await vscode.window.showTextDocument(doc, { preserveFocus: false });
          const pos = new vscode.Position(Math.max(0, line), 0);
          editor.selection = new vscode.Selection(pos, pos);
          editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenterIfOutsideViewport);
          await vscode.commands.executeCommand("editor.action.showHover");
          return;
        }
        if (markdown) {
          const plain = markdown.replace(/\*\*/g, "").replace(/\n+/g, " — ");
          void vscode.window.showInformationMessage(plain.slice(0, 280));
        }
      },
    ),
    vscode.commands.registerCommand(
      "focus.whyEdge",
      async (evidence?: ImportEvidence[], reason?: string) => {
        await showWhyEdge(evidence, reason);
      },
    ),
    vscode.commands.registerCommand("focus.refresh", () => runAudit(true, extVersion)),
  );

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        gutter.apply(editor);
        inlineExplanation.apply(editor);
        scheduleQuietAuditForDiff(editor, extVersion);
      }
    }),
    // Focus reads git/disk — refresh after save so rails update in place (no Reload).
    vscode.workspace.onDidSaveTextDocument((document) => {
      scheduleAutoAudit(document, extVersion);
    }),
    // Unsaved buffer → overlay audit so rails track what you see before Save.
    vscode.workspace.onDidChangeTextDocument((event) => {
      scheduleLiveOverlayAudit(event.document, extVersion);
    }),
  );

  // Do not auto-audit on window open — Tree-sitter JS workers can SIGSEGV on
  // some files and macOS pops "Python quit unexpectedly" even when Focus recovers.
  // Rails still refresh on save / live overlay / explicit Audit Local.
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

/**
 * When opening an SCM / Working Tree side-by-side diff with no HUD yet,
 * quietly audit so rails appear on the modified (file:) pane.
 */
function scheduleQuietAuditForDiff(editor: vscode.TextEditor, extVersion: string): void {
  if (lastHud) {
    return;
  }
  if (editor.document.uri.scheme !== "file") {
    return;
  }
  if (!SOURCE_LANGUAGE_IDS.has(editor.document.languageId)) {
    return;
  }
  if (!editorIsDiffPane(editor)) {
    return;
  }
  const root = workspaceRoot();
  if (!root) {
    return;
  }
  const rel = path.relative(root, editor.document.uri.fsPath);
  if (!rel || rel.startsWith("..")) {
    return;
  }

  if (diffAuditTimer) {
    clearTimeout(diffAuditTimer);
  }
  diffAuditTimer = setTimeout(() => {
    diffAuditTimer = undefined;
    void runAudit(true, extVersion);
  }, DIFF_AUDIT_DEBOUNCE_MS);
}

function setHud(hud: FocusHUD, root: string, extVersion: string): void {
  lastHud = hud;
  lenses.refresh(hud, root);
  gutter.refresh(hud, root);
  inlineExplanation.refresh(hud, root);
  statusBar.text = `Focus · ${hud.risk_tier}`;
  statusBar.tooltip = `${hud.summary}\n\nFocus extension v${extVersion}`;
}

function liveBufferOverlayEnabled(): boolean {
  return vscode.workspace.getConfiguration("focus").get<boolean>("liveBufferOverlay", true);
}

function scheduleLiveOverlayAudit(document: vscode.TextDocument, extVersion: string): void {
  if (!liveBufferOverlayEnabled()) {
    return;
  }
  if (!document.isDirty) {
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
  const rel = path.relative(root, document.uri.fsPath).split(path.sep).join("/");
  if (!rel || rel.startsWith("..")) {
    return;
  }

  if (liveOverlayTimer) {
    clearTimeout(liveOverlayTimer);
  }
  liveOverlayTimer = setTimeout(() => {
    liveOverlayTimer = undefined;
    void runAudit(true, extVersion, /* withOverlay */ true);
  }, LIVE_OVERLAY_DEBOUNCE_MS);
}

function collectOverlayPayload(root: string): Record<string, string> | undefined {
  const overlays: Record<string, string> = {};
  const docs = vscode.workspace.textDocuments
    .filter(
      (doc) =>
        doc.isDirty &&
        doc.uri.scheme === "file" &&
        SOURCE_LANGUAGE_IDS.has(doc.languageId),
    )
    .slice(0, MAX_OVERLAY_FILES);

  // Prefer the active editor's dirty doc first.
  const active = vscode.window.activeTextEditor?.document;
  const ordered = active
    ? [active, ...docs.filter((d) => d.uri.toString() !== active.uri.toString())]
    : docs;

  for (const doc of ordered.slice(0, MAX_OVERLAY_FILES)) {
    const rel = path.relative(root, doc.uri.fsPath).split(path.sep).join("/");
    if (!rel || rel.startsWith("..")) {
      continue;
    }
    overlays[rel] = doc.getText();
  }
  return Object.keys(overlays).length ? overlays : undefined;
}

function activeEditorRelPath(root: string): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.uri.scheme !== "file") {
    return undefined;
  }
  const rel = path.relative(root, editor.document.uri.fsPath).split(path.sep).join("/");
  if (!rel || rel.startsWith("..")) {
    return undefined;
  }
  return rel;
}

async function runAudit(
  quiet = false,
  extVersion = "dev",
  withOverlay = false,
): Promise<void> {
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
    let overlayPath: string | undefined;
    // Any new audit invalidates an in-flight LLM enrich from an older run.
    const enrichGen = ++llmEnrichGeneration;
    try {
      if (withOverlay && liveBufferOverlayEnabled()) {
        const payload = collectOverlayPayload(root);
        if (payload) {
          overlayPath = path.join(
            os.tmpdir(),
            `focus-overlay-${process.pid}-${Date.now()}.json`,
          );
          fs.writeFileSync(overlayPath, JSON.stringify(payload), "utf8");
        }
      }
      const settingOn = vscode.workspace
        .getConfiguration("focus")
        .get<boolean>("llmCaptions", false);
      // Option A: Audit Local waits for LLM on the open file before first paint
      // (no short deterministic flash). Save/overlay stay deterministic-only.
      const wantLlmAuditLocal =
        !quiet && !withOverlay && settingOn && !overlayPath;

      if (wantLlmAuditLocal) {
        const activeRel = activeEditorRelPath(root);
        let hud: FocusHUD;
        try {
          hud = await vscode.window.withProgress(
            {
              location: vscode.ProgressLocation.Window,
              title: activeRel
                ? "Focus: auditing + labeling open file…"
                : "Focus: auditing + labeling captions…",
            },
            () =>
              auditLocal(root, undefined, {
                allowLlm: true,
                llmPaths: activeRel ? [activeRel] : undefined,
              }),
          );
        } catch (err) {
          // Fail open to deterministic rails if LLM path errors.
          reportError(err, true);
          hud = await vscode.window.withProgress(
            {
              location: vscode.ProgressLocation.Window,
              title: "Focus: auditing local changes…",
            },
            () => auditLocal(root, undefined, { allowLlm: false }),
          );
          if (enrichGen !== llmEnrichGeneration) {
            return;
          }
          setHud(hud, root, extVersion);
          if (!quiet) {
            HudPanel.show(hud);
          }
          return;
        }
        if (enrichGen !== llmEnrichGeneration) {
          return;
        }
        setHud(hud, root, extVersion);
        if (!quiet) {
          HudPanel.show(hud);
        }
        // Label remaining files in the background (open file already long).
        if (activeRel) {
          statusBar.text = `Focus · ${hud.risk_tier} · labeling…`;
          statusBar.tooltip = `${hud.summary}\n\nFocus extension v${extVersion}\nLLM captions finishing other files…`;
          void (async () => {
            try {
              const labeled = await vscode.window.withProgress(
                {
                  location: vscode.ProgressLocation.Window,
                  title: "Focus: labeling remaining captions…",
                },
                () => auditLocal(root, undefined, { allowLlm: true }),
              );
              if (enrichGen !== llmEnrichGeneration) {
                return;
              }
              setHud(labeled, root, extVersion);
            } catch (err) {
              if (enrichGen !== llmEnrichGeneration) {
                return;
              }
              reportError(err, true);
              statusBar.text = `Focus · ${hud.risk_tier}`;
              statusBar.tooltip = `${hud.summary}\n\nFocus extension v${extVersion}`;
            }
          })();
        }
        return;
      }

      const hud = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Window,
          title: "Focus: auditing local changes…",
        },
        () =>
          auditLocal(root, overlayPath, {
            allowLlm: false,
          }),
      );
      if (enrichGen !== llmEnrichGeneration) {
        return;
      }
      setHud(hud, root, extVersion);
      if (!quiet) {
        HudPanel.show(hud);
      }
    } catch (err) {
      reportError(err, quiet);
    } finally {
      if (overlayPath) {
        try {
          fs.unlinkSync(overlayPath);
        } catch {
          // temp cleanup best-effort
        }
      }
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

/**
 * "Why this edge" — jump to the import statement that proves a blast-radius edge.
 *
 * Evidence is deterministic (Focus copies it from the parser); we never infer a
 * line here. One proof → jump straight there; several → let the user pick which
 * proving import to open. No evidence → fall back to the reason text + HUD.
 */
async function showWhyEdge(
  evidence?: ImportEvidence[],
  reason?: string,
): Promise<void> {
  const proofs = (evidence ?? []).filter((e) => e && e.path && e.line > 0);
  if (proofs.length === 0) {
    if (reason) {
      const pick = await vscode.window.showInformationMessage(`Focus: ${reason}`, "Open HUD");
      if (pick === "Open HUD" && lastHud) {
        HudPanel.show(lastHud);
      }
    } else if (lastHud) {
      HudPanel.show(lastHud);
    }
    return;
  }

  let chosen = proofs[0];
  if (proofs.length > 1) {
    const items = proofs.map((e) => ({
      label: `${e.path}:${e.line}`,
      description: `imports ${e.module}`,
      evidence: e,
    }));
    const picked = await vscode.window.showQuickPick(items, {
      title: "Focus · why this edge",
      placeHolder: "Jump to the import that proves this dependency",
    });
    if (!picked) {
      return;
    }
    chosen = picked.evidence;
  }

  await openImportEvidence(chosen);
}

async function openImportEvidence(evidence: ImportEvidence): Promise<void> {
  const root = workspaceRoot();
  if (!root) {
    void vscode.window.showWarningMessage(workspaceRootError());
    return;
  }
  const target = vscode.Uri.file(path.join(root, evidence.path));
  try {
    const doc = await vscode.workspace.openTextDocument(target);
    const editor = await vscode.window.showTextDocument(doc, { preserveFocus: false });
    const line = Math.max(0, Math.min(evidence.line - 1, doc.lineCount - 1));
    const range = doc.lineAt(line).range;
    editor.selection = new vscode.Selection(range.start, range.end);
    editor.revealRange(range, vscode.TextEditorRevealType.InCenterIfOutsideViewport);
  } catch {
    void vscode.window.showWarningMessage(
      `Focus: could not open ${evidence.path}:${evidence.line}`,
    );
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
