import { execFile } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { promisify } from "node:util";
import * as vscode from "vscode";

import type { FocusHUD } from "./types";

const execFileAsync = promisify(execFile);

export class FocusCliError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FocusCliError";
  }
}

export function resolveFocusBinary(): string {
  const configured = vscode.workspace
    .getConfiguration("focus")
    .get<string>("path")
    ?.trim();
  if (configured && fs.existsSync(configured)) {
    return configured;
  }
  // Prefer the editable repo venv over a stale/crashing `focus` on PATH
  // (uv tool installs have been known to SIGSEGV on macOS Tree-sitter).
  const root = workspaceRoot();
  if (root) {
    const venvFocus = path.join(root, ".venv", "bin", "focus");
    if (fs.existsSync(venvFocus)) {
      return venvFocus;
    }
  }
  return "focus";
}

export function workspaceRoot(): string | undefined {
  const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!folder) {
    return undefined;
  }
  const gitRoot = findGitRoot(folder);
  if (!gitRoot) {
    return undefined;
  }
  return gitRoot;
}

export function workspaceRootError(): string {
  const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!folder) {
    return "Focus: open a folder workspace first (File → Open Folder → your repo).";
  }
  return (
    `Focus: "${folder}" is not a git repository. ` +
    "Open the project root (the folder that contains `.git`), e.g. `…/Focus` — not the parent `Cursor` folder."
  );
}

function findGitRoot(start: string): string | undefined {
  let dir = path.resolve(start);
  while (true) {
    if (fs.existsSync(path.join(dir, ".git"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      return undefined;
    }
    dir = parent;
  }
}

async function runFocus(args: string[], cwd: string): Promise<string> {
  const bin = resolveFocusBinary();
  try {
    const { stdout, stderr } = await execFileAsync(bin, args, {
      cwd,
      maxBuffer: 20 * 1024 * 1024,
      env: { ...process.env },
    });
    if (stderr && !stdout.trim()) {
      throw new FocusCliError(stderr.trim());
    }
    return stdout;
  } catch (err: unknown) {
    const e = err as {
      code?: string | number;
      message?: string;
      stderr?: string;
      stdout?: string;
      signal?: string;
    };
    if (e.code === "ENOENT") {
      throw new FocusCliError(
        "focus not found on PATH. Install with: pip install \"focus-hud>=0.3.3\" " +
          "(or set focus.path). See https://pypi.org/project/focus-hud/",
      );
    }
    // 139 / SIGSEGV — native Tree-sitter crash (should be rare after JS worker isolation).
    if (e.code === 139 || e.signal === "SIGSEGV") {
      throw new FocusCliError(
        "focus crashed (segfault) while auditing — usually a stale global `focus` on PATH. " +
          "Set focus.path to this repo's .venv/bin/focus (already in .vscode/settings.json), " +
          "re-run ./scripts/install-extension.sh, then Developer: Reload Window. " +
          "CLI check: .venv/bin/focus audit --local --format json",
      );
    }
    const detail = (e.stderr || e.stdout || e.message || String(err)).trim();
    throw new FocusCliError(detail || "focus command failed");
  }
}

function parseHudJson(stdout: string): FocusHUD {
  const text = stdout.trim();
  // CLI may prefix "Wrote Focus HUD to …" when --out is used; we don't use --out.
  const start = text.indexOf("{");
  if (start < 0) {
    throw new FocusCliError("focus did not return JSON (need focus-hud>=0.2.0 with --format json)");
  }
  return JSON.parse(text.slice(start)) as FocusHUD;
}

export type AuditLocalOptions = {
  /**
   * When true, LLM captions may run if `focus.llmCaptions` is on.
   * Autosave / live overlay / quiet refresh must pass false so rails stay fast
   * even when FOCUS_LLM_ENABLED=true in `.env`.
   */
  allowLlm?: boolean;
  /**
   * Repo-relative paths to label first (visible-file-first). When set with
   * allowLlm, passes `--llm-path` so only those files hit the model.
   */
  llmPaths?: string[];
};

export async function auditLocal(
  root: string,
  overlayFile?: string,
  options?: AuditLocalOptions,
): Promise<FocusHUD> {
  const base =
    vscode.workspace.getConfiguration("focus").get<string>("base") || "main";
  const args = ["audit", "--local", "--base", base, "--path", root, "--format", "json"];
  if (overlayFile) {
    args.push("--overlay-file", overlayFile);
  }
  // Prefer --llm-captions only when wanted. Do not pass --no-llm-captions:
  // older focus-hud installs on PATH lack that flag and toast a Typer error.
  const settingOn = vscode.workspace
    .getConfiguration("focus")
    .get<boolean>("llmCaptions", false);
  const wantLlm = Boolean(options?.allowLlm) && settingOn && !overlayFile;
  if (wantLlm) {
    args.push("--llm-captions");
    for (const rel of options?.llmPaths ?? []) {
      const cleaned = rel.replace(/\\/g, "/").replace(/^\.\//, "");
      if (cleaned) {
        args.push("--llm-path", cleaned);
      }
    }
  }
  const stdout = await runFocus(args, root);
  return parseHudJson(stdout);
}

export async function traceFile(
  root: string,
  filePath: string,
): Promise<FocusHUD> {
  const stdout = await runFocus(
    ["trace", filePath, "--root", root, "--format", "json"],
    root,
  );
  return parseHudJson(stdout);
}
