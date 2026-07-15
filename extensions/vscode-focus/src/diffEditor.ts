import * as vscode from "vscode";

/** True when this editor belongs to a text-diff tab (SCM Working Tree, etc.). */
export function editorIsDiffPane(editor: vscode.TextEditor): boolean {
  const uri = editor.document.uri.toString();
  for (const group of vscode.window.tabGroups.all) {
    for (const tab of group.tabs) {
      const input = tab.input;
      if (
        input instanceof vscode.TabInputTextDiff &&
        (input.original.toString() === uri || input.modified.toString() === uri)
      ) {
        return true;
      }
    }
  }
  return false;
}
