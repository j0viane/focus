Sideload this extension to see Focus **in the diff**: CodeLens on changed **symbols**, gutter highlights, and a HUD webview.

## Prerequisites

```bash
pip install "focus-hud>=0.2.0"
# or: uv tool install focus-hud --force --python 3.13
focus version   # must support --format json
```

## Install (easiest)

From repo root:

```bash
./scripts/install-extension.sh
```

Then **Cmd+Shift+P → Developer: Reload Window** in Cursor / VS Code.

## Develop

```bash
cd extensions/vscode-focus
npm install
npm run compile
./scripts/install-extension.sh   # from repo root
```

## Commands

- **Focus: Audit Local Changes** — `focus audit --local --format json`
- **Focus: Trace Current File** — `focus trace <file> --format json`
- **Focus: Show HUD** — open the last HUD panel
- **Focus: Show Why** — blast-radius reason (from CodeLens on Danger Zone files)
- **Focus: Refresh** — re-run audit for CodeLens + gutter

## What you should see (inline explanations)

Virtual UI only — **not** written to disk or git.

```text
🎯 Focus · _extract_definitions · 🔴 CRITICAL · 22 downstream
   Part of a CRITICAL blast radius — 22 downstream files may be affected.

    def _extract_definitions(tree: ast.AST) -> list[Definition]:
        ...
                ℹ️ Records this as a function in the AST (Abstract Syntax Tree).
                Definition(..., kind="function", ...)
                ℹ️ Records this as a class in the AST (Abstract Syntax Tree).
                Definition(..., kind="class", ...)
```

| Surface | Where |
|---|---|
| **🎯 Focus header** | Above each changed `def` / `class` — risk + downstream + short summary |
| **ℹ️ Detail** | Above each contiguous edit block — hunk-local copy (not the parent function name) |
| **Gutter / tint** | Highlight on every git-touched line for that symbol |
| **File CodeLens** | Blast-radius files without symbol overlap (Danger Zone / hops) |
| **HUD panel** | Full Mermaid + Danger Zones |

Toggle gutter: `focus.gutter`. Toggle inline explainers: `focus.inlineExplanations`.

## Settings

| Setting | Meaning |
|---|---|
| `focus.path` | Absolute path to `focus` binary (optional) |
| `focus.base` | Git base for `--local` (default `main`) |
| `focus.gutter` | Gutter + line highlights (default `true`) |
| `focus.inlineExplanations` | ℹ️ detail rows on edit blocks (default `true`) |
| `focus.lensFontSize` | CodeLens size: `0` = editor default, `-1` = match `editor.fontSize` |
