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

**SCM Working Tree:** open a changed Python/JS/TS file from Source Control — the **modified (right) side** shows the same risk rail + ℹ️ when `diffEditor.codeLens` is on (Focus enables this by default). Left/base pane stays quiet.

## What you should see (inline explanations)

Virtual UI only — **not** written to disk or git:

```text
🔴 CRITICAL — `focus audit` → IDE captions — bad copy misleads every local review.
    def _build_hunk_details(
        symbol: ChangedSymbolInfo,
        facts: ModuleFacts | None,
        purpose_fallback: str,
        *,
        purpose_is_curated: bool = False,
    ) -> list[HunkDetail]:
        """Build ℹ️ rows: one outcome per symbol unless hunks teach different outcomes."""
        ...
        for run in runs:
            ℹ️ Builds each edit's caption (plain English above the changed lines).
            detail = _hybrid_detail_for_hunk(
                run_text,
                facts=facts,
                hunk_lines=run,
                symbol_name=symbol.name,
                purpose_fallback=purpose_fallback,
            )
            out.append(HunkDetail(line=anchor, changed_lines=run, detail=detail))
        return _collapse_hunk_details_to_outcomes(...)
```

Risk rail above `def`; ℹ️ above the changed lines. A second ℹ️ appears only when two hunks teach **different** outcomes (e.g. function vs class).

| Surface | Where |
|---|---|
| **Risk rail** | Above each changed `def` / `class` — `{emoji} {RISK} — {who} — {what goes wrong}` (quiet when LOW) |
| **ℹ️ Purpose** | Above the primary edit (or each distinct outcome) — what this edit does |
| **Trust cues** | Hover the **highlighted code** (or click the rail / ℹ️) — ≤2 proven/heuristic cues. CodeLens title tooltips alone are flaky on macOS. |
| **SCM diff (modified)** | Same rails on the Working Tree right pane (not the base/left side; no tint in diffs) |
| **Gutter / tint** | Highlight on every git-touched line for that symbol (normal editor only) |
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
