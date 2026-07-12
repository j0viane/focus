# Focus VS Code / Cursor extension

Sideload this extension to see Focus **in the editor**: CodeLens on changed files + a HUD webview.

## Prerequisites

```bash
pip install "focus-hud>=0.2.0"
# or: uv tool install focus-hud --python 3.13
focus version   # must support --format json
```

## Develop

```bash
cd extensions/vscode-focus
npm install
npm run compile
```

In Cursor / VS Code: **Run and Debug → Extension Development Host**, or:

```bash
code --extensionDevelopmentPath=extensions/vscode-focus
```

## Commands

- **Focus: Audit Local Changes** — `focus audit --local --format json`
- **Focus: Trace Current File** — `focus trace <file> --format json`
- **Focus: Show HUD** — open the last HUD panel
- **Focus: Refresh** — re-run audit for CodeLens

## Settings

| Setting | Meaning |
|---|---|
| `focus.path` | Absolute path to `focus` binary (optional) |
| `focus.base` | Git base for `--local` (default `main`) |
