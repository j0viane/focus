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

## What you should see (Phase 4 deepen)

| Surface | Where |
|---|---|
| **Symbol CodeLens** | On each **changed function/class line** (`Focus · validate_token · HIGH · N downstream`) |
| **File CodeLens** | On blast-radius files without symbol overlap (Danger Zone / hops) |
| **Gutter** | Tint on changed symbol lines; Danger Zone / downstream files highlighted at top |
| **HUD panel** | Full Mermaid + Danger Zones (unchanged) |

Toggle gutter: `focus.gutter` in settings.

## Settings

| Setting | Meaning |
|---|---|
| `focus.path` | Absolute path to `focus` binary (optional) |
| `focus.base` | Git base for `--local` (default `main`) |
| `focus.gutter` | Gutter + line highlights (default `true`) |
