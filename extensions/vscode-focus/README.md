Sideload this extension to see Focus **in the diff**: risk rail + ℹ️ on changed **symbols**, gutter highlights, and a HUD webview.

## Prerequisites

```bash
pip install "focus-hud>=0.3.3"
# or: uv tool install focus-hud --force --python 3.13
focus version   # must support --format json (0.3.3+)
```

## Install (easiest)

From repo root:

```bash
./scripts/install-extension.sh
```

Installs editable `focus-hud` + packages extension 0.5.4+. Then **Reload Window**.

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
- **Focus: Refresh** — re-run audit for CodeLens + gutter

**Default dogfood loop:** edit a real line — rails update live from the unsaved buffer (`focus.liveBufferOverlay`). **Save** still syncs disk (`focus.autoAuditOnSave`). Use Audit Local when you want the HUD panel or a forced refresh.

**Where rails show:** the **open file** and the SCM **Working Tree** modified (right) pane — Focus enables both `editor.codeLens` and `diffEditor.codeLens`. Left/base diff pane stays quiet.

**Live buffer:** with `focus.liveBufferOverlay` (default on), dirty unsaved edits refresh rails after a short debounce — no Save required.

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

Risk rail above `def`; ℹ️ describes **this edit** (return, call, import, `Added N blank lines.`, …) — not a static slogan. A second ℹ️ appears only when two edit blocks teach **different** outcomes.

| Surface | Where |
|---|---|
| **Risk rail** | Above each changed `def` / `class` — `{emoji} {RISK} — {who} — {what goes wrong}` (quiet when LOW) |
| **ℹ️ caption** | Edit-shaped detail at the change (return / call / import / assign / blank count / …) — **still shown on LOW** (narrate the edit, not the alarm) |
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
| `focus.liveBufferOverlay` | While editing (dirty buffer), quietly re-audit via overlay — no Save needed (default `true`) |
| `focus.llmCaptions` | Opt-in: on **Focus: Audit Local**, show deterministic rails immediately, then LLM-label the **open file first** and the rest in the background (pack-hash cache + parallel; never autosave / overlay). Needs `FOCUS_LLM_API_KEY` or `FOCUS_LLM_PROVIDER=ollama` (default `qwen2.5-coder:3b`). |
| `focus.lensFontSize` | CodeLens size: `0` = editor default, `-1` = match `editor.fontSize` |
