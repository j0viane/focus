import * as path from "node:path";
import * as vscode from "vscode";

import { definitionLine, editorLine, highlightLines, hunkDetailAtLine, lineInSymbol } from "./symbolLayout";
import { evidenceMarkdown } from "./explainText";
import { editorIsDiffPane } from "./diffEditor";
import type { FocusHUD } from "./types";

/** Soft tint on every git-touched line for changed symbols. */
export class InlineExplanation {
  private hud: FocusHUD | undefined;
  private root: string | undefined;
  private readonly lineTint: vscode.TextEditorDecorationType;

  constructor() {
    this.lineTint = vscode.window.createTextEditorDecorationType({
      isWholeLine: true,
      backgroundColor: "rgba(78, 201, 176, 0.06)",
    });
  }

  dispose(): void {
    this.lineTint.dispose();
  }

  refresh(hud: FocusHUD | undefined, root: string | undefined): void {
    this.hud = hud;
    this.root = root;
    this.applyAll();
  }

  applyAll(): void {
    for (const editor of vscode.window.visibleTextEditors) {
      this.apply(editor);
    }
  }

  apply(editor: vscode.TextEditor): void {
    if (!enabled() || !this.hud || !this.root) {
      editor.setDecorations(this.lineTint, []);
      return;
    }

    // Line tint fights CodeLens spacers in side-by-side SCM diffs — CodeLens only there.
    if (editorIsDiffPane(editor) || editor.document.uri.scheme !== "file") {
      editor.setDecorations(this.lineTint, []);
      return;
    }

    const rel = relPath(this.root, editor.document.uri.fsPath);
    if (!rel) {
      editor.setDecorations(this.lineTint, []);
      return;
    }

    const seen = new Set<number>();
    const decorations: vscode.DecorationOptions[] = [];
    for (const sym of this.hud.changed_symbols) {
      if (sym.path !== rel) {
        continue;
      }
      // Decoration carry hoverMessage — reliable every time (unlike CodeLens title tooltips on macOS).
      const trust = new vscode.MarkdownString(evidenceMarkdown(sym));
      trust.isTrusted = true;
      for (const line of highlightLines(sym)) {
        if (
          line < editor.document.lineCount &&
          !seen.has(line) &&
          !editor.document.lineAt(line).isEmptyOrWhitespace
        ) {
          seen.add(line);
          decorations.push({
            range: editor.document.lineAt(line).range,
            hoverMessage: trust,
          });
        }
      }
      // Also attach trust on the def line (rail sits above it).
      const def = definitionLine(sym);
      if (def < editor.document.lineCount && !seen.has(def)) {
        seen.add(def);
        decorations.push({
          range: editor.document.lineAt(def).range,
          hoverMessage: trust,
        });
      }
    }
    for (const note of this.hud.line_explanations ?? []) {
      if (note.path !== rel) {
        continue;
      }
      const trust = new vscode.MarkdownString(note.detail);
      trust.isTrusted = true;
      for (const oneBased of note.changed_lines?.length ? note.changed_lines : [note.line]) {
        const line = editorLine(oneBased);
        if (
          line < editor.document.lineCount &&
          !seen.has(line) &&
          !editor.document.lineAt(line).isEmptyOrWhitespace
        ) {
          seen.add(line);
          decorations.push({
            range: editor.document.lineAt(line).range,
            hoverMessage: trust,
          });
        }
      }
    }
    editor.setDecorations(this.lineTint, decorations);
  }

  provideHover(
    document: vscode.TextDocument,
    position: vscode.Position,
  ): vscode.ProviderResult<vscode.Hover> {
    if (!this.hud || !this.root) {
      return undefined;
    }
    const rel = relPath(this.root, document.uri.fsPath);
    if (!rel) {
      return undefined;
    }

    for (const sym of this.hud.changed_symbols) {
      if (sym.path !== rel || !lineInSymbol(sym, position)) {
        continue;
      }
      const hunk = hunkDetailAtLine(sym, position.line + 1);
      const purpose =
        hunk?.detail ||
        (position.line === definitionLine(sym) ? undefined : sym.detail);
      const md = new vscode.MarkdownString(evidenceMarkdown(sym, purpose));
      if (md.value) {
        md.isTrusted = true;
        return new vscode.Hover(md);
      }
    }

    for (const note of this.hud.line_explanations ?? []) {
      if (note.path !== rel) {
        continue;
      }
      const touched = note.changed_lines?.length ? note.changed_lines : [note.line];
      if (!touched.some((line) => editorLine(line) === position.line)) {
        continue;
      }
      const md = new vscode.MarkdownString(note.detail);
      md.isTrusted = true;
      return new vscode.Hover(md);
    }

    return undefined;
  }
}

export function inlineExplanationsEnabled(): boolean {
  return vscode.workspace.getConfiguration("focus").get<boolean>("inlineExplanations", true);
}

function enabled(): boolean {
  return inlineExplanationsEnabled();
}

function relPath(root: string, fsPath: string): string | undefined {
  const rel = path.relative(root, fsPath).split(path.sep).join("/");
  if (!rel || rel.startsWith("..")) {
    return undefined;
  }
  return rel;
}
