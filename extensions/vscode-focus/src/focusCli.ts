import { execFile } from "node:child_process";
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
  if (configured) {
    return configured;
  }
  return "focus";
}

export function workspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
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
    const e = err as { code?: string; message?: string; stderr?: string };
    if (e.code === "ENOENT") {
      throw new FocusCliError(
        "focus not found on PATH. Install with: pip install \"focus-hud>=0.2.0\" " +
          "(or set focus.path). See https://pypi.org/project/focus-hud/",
      );
    }
    const detail = (e.stderr || e.message || String(err)).trim();
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

export async function auditLocal(root: string): Promise<FocusHUD> {
  const base =
    vscode.workspace.getConfiguration("focus").get<string>("base") || "main";
  const stdout = await runFocus(
    ["audit", "--local", "--base", base, "--path", root, "--format", "json"],
    root,
  );
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
