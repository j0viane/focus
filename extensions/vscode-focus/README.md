Sideload this extension to see Focus **in the diff**: risk rail + ℹ️ on changed **symbols**, gutter highlights, and a HUD webview.

## Prerequisites

```bash
pip install "focus-hud>=0.3.1"
# or: uv tool install focus-hud --force --python 3.13
focus version   # must support --format json (0.3.1+)
```

## Install (easiest)

From repo root:

```bash
./scripts/install-extension.sh   # packages extension 0.5.1+
```

Then **Cmd+Shift+P → Developer: Reload Window** in Cursor / VS Code (once after install).

## Develop

```bash
cd extensions/vscode-focus
npm install
npm run compile
./scripts/install-extension.sh   # from repo root
```

## Commands

- **Focus: Audit Local Changes** — `focus audit --local --format json` (first run / open HUD)
- **Focus: Trace Current File** — `focus trace <file> --format json`
- **Focus: Show HUD** — open the last HUD panel
- **Focus: Show Why** — blast-radius reason (from CodeLens on Danger Zone files)
- **Focus: Refresh** — re-run audit for CodeLens + gutter

**Default dogfood loop:** edit a real line → **Save** → rails refresh in place (`focus.autoAuditOnSave`). Use Audit Local when you want the HUD panel or a forced refresh.

## What you should see (inline explanations)

Virtual UI only — **not** written to disk or git.

One outcome per symbol (typical):

```text
🔴 CRITICAL — `focus audit` → IDE captions — bad copy misleads every local review.
    def _build_hunk_details(...):
ℹ️ Builds each edit's caption (plain English above the changed lines).
```

Two ℹ️ only when hunks teach **different** outcomes:

```text
🔴 CRITICAL — Builds Focus's list of functions/classes — bad parses → wrong blast radius.
    def _extract_definitions(tree: ast.AST) -> list[Definition]:
        ...
ℹ️ Records this as a function in the AST (Abstract Syntax Tree).
                Definition(..., kind="function", ...)
ℹ️ Records this as a class in the AST (Abstract Syntax Tree).
                Definition(..., kind="class", ...)
```

| Surface | Where |
|---|---|
| **Risk rail** | Above each changed `def` / `class` — `{emoji} {RISK} — {who} — {what goes wrong}` (quiet when LOW) |
| **ℹ️ Purpose** | Above the primary edit (or each distinct outcome) — what this edit does |
| **Hover** | On the rail or ℹ️ — proven vs heuristic evidence |
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
| `focus.inlineExplanations` | ℹ️ purpose rows on edit blocks (default `true`) |
| `focus.autoAuditOnSave` | After Save, quietly re-audit and refresh CodeLens (default `true`) |
| `focus.lensFontSize` | CodeLens size: `0` = editor default, `-1` = match `editor.fontSize` |
