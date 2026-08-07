Sideload this extension to see Focus **in the diff**: ℹ️ on changed **symbols**, gutter highlights, and a HUD webview.

## Prerequisites

```bash
# Prefer editable install from this repo (tracks main):
#   ./scripts/install-extension.sh
# Or PyPI:
pip install "focus-hud>=0.3.5"
focus version   # must support --format json
```

## Install (easiest)

From repo root:

```bash
./scripts/install-extension.sh
```

Installs editable `focus-hud` + packages extension **0.5.15**. Then **Reload Window**.

## Develop

```bash
cd extensions/vscode-focus
npm install
npm run compile
cd ../..
./scripts/install-extension.sh
```

## Commands

- **Focus: Audit Local Changes** — `focus audit --local --format json` (first run / open HUD)
- **Focus: Trace Current File** — `focus trace <file> --format json`
- **Focus: Show HUD** — open the last HUD panel
- **Focus: Show Why** — blast-radius reason (from CodeLens on Danger Zone files)
- **Focus: Why This Edge (jump to proving import)** — from the file CodeLens on a blast-radius file, jump the editor to the exact `import` line that proves the dependency edge (evidence, never inferred). On the changed file it lists every dependent's import; on a direct dependent it opens that file's own import line. Transitive (2+ hop) files have no single proving line and fall back to the reason text.
- **Focus: Refresh** — re-run audit for CodeLens + gutter

**Default dogfood loop:** edit a real line — ℹ️ updates live from the unsaved buffer (`focus.liveBufferOverlay`). **Save** still syncs disk (`focus.autoAuditOnSave`). Use Audit Local when you want the HUD panel or a forced refresh.

**Where ℹ️ show:** the **open file** and the SCM **Working Tree** modified (right) pane — Focus enables both `editor.codeLens` and `diffEditor.codeLens`. Left/base diff pane stays quiet.

**Live buffer:** with `focus.liveBufferOverlay` (default on), dirty unsaved edits refresh ℹ️ after a short debounce — no Save required.

## What you should see (inline explanations)

Virtual UI only — **not** written to disk or git:

```text
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
            ℹ️ Returns `2`.
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

ℹ️ describes **this edit** (return, call, import, `Added N blank lines.`, …) — not a static slogan. Risk / who-breaks lives in the **HUD** (and PR comment), not as a second CodeLens on `def`. A second ℹ️ appears only when two edit blocks teach **different** outcomes.

| Surface | Where |
|---|---|
| **ℹ️ caption** | Edit-shaped detail at the change (return / call / import / assign / blank count / …) — **still shown on LOW** (narrate the edit, not the alarm) |
| **Trust cues** | Hover the **highlighted code** (or click the ℹ️) — ≤2 proven/heuristic cues. CodeLens title tooltips alone are flaky on macOS. |
| **SCM diff (modified)** | Same ℹ️ on the Working Tree right pane (not the base/left side; no tint in diffs) |
| **Gutter / tint** | Highlight on every git-touched line for that symbol (normal editor only) |
| **File CodeLens** | Blast-radius files without symbol overlap (Danger Zone / hops) |
| **HUD panel** | Full Mermaid + Danger Zones + risk / implication |

Toggle gutter: `focus.gutter`. Toggle inline explainers: `focus.inlineExplanations`.

## Settings

| Setting | Meaning |
|---|---|
| `focus.path` | Absolute path to `focus` binary (optional) |
| `focus.base` | Git base for `--local` (default `main`) |
| `focus.gutter` | Gutter + line highlights (default `true`) |
| `focus.inlineExplanations` | ℹ️ purpose rows on edit blocks (default `true`) |
| `focus.autoAuditOnSave` | After Save, quietly re-audit and refresh CodeLens (default `true`) |
| `focus.liveBufferOverlay` | While editing (dirty buffer), quietly re-audit via overlay — no Save needed (default `true`) |
| `focus.llmCaptions` | Opt-in: on **Focus: Audit Local**, wait for LLM on the **open file** before painting (no short flash), then label the rest in the background (pack-hash cache + parallel; never autosave / overlay). Needs `FOCUS_LLM_API_KEY` or `FOCUS_LLM_PROVIDER=ollama` (default `qwen2.5-coder:3b`). |
| `focus.lensFontSize` | CodeLens size: `0` = editor default, `-1` = match `editor.fontSize` |
