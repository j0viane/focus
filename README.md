# Focus

**Blast radius you can defend — evidence-only, before you merge.**

When a senior asks *why* on an AI-assisted PR, “the model wrote it” isn’t an answer.  
Focus shows **what else that change touches** — with evidence you can point at in review.

---

## Who · What · When · Where · Why · How

| | |
|---|---|
| **Who** | Juniors shipping AI-assisted PRs, and seniors who have to review them — anyone who must **defend** a change |
| **What** | An evidence-only blast-radius HUD: import graph → Mermaid map + Danger Zones. No LLM inventing edges |
| **When** | Right before you push, and on every PR — the moment someone asks “what else breaks?” or “why this?” |
| **Where** | **A:** GitHub PR comment (full HUD). **C:** inline in the diff — IDE CodeLens + HUD panel now; GitHub file annotations next. **Not** committed `.md` files |
| **Why** | AI made teams faster at generating code and slower at shared understanding. The feedback loop breaks when the answer is silence |
| **How** | Parse the repo → dependency graph → reverse-BFS from the diff → quiet unless it matters. Same `FocusHUD` everywhere (`--format json` for the IDE) |

> Not another AI PR summary. Not a hop inventory that cries wolf on every file.

---

## Try in 60 seconds

```bash
pip install "focus-hud>=0.3.3"
# or: uv tool install focus-hud

focus trace path/to/shared_module.py --out focus-hud.md
# open focus-hud.md → Markdown preview for Mermaid

focus audit --local --out focus-hud.md   # local preview only (gitignored — not committed)
focus audit --local --format json        # machine-readable HUD (IDE / tools)
```

`focus-hud.md` is a **scratch file** for local Mermaid preview. Focus does **not** ask you to commit HUD output — reviewers get **A** (PR comment) and **C** (inline in the diff).

**Demo fixture (no app required):**

```bash
git clone https://github.com/j0viane/focus.git && cd focus
uv sync
uv run focus trace tests/fixtures/glass_box/auth_utils.py \
  --root tests/fixtures/glass_box --out focus-hud.md
```

Gallery + walkthrough: [`docs/DEMO.md`](docs/DEMO.md) · [`docs/assets/`](docs/assets/)

---

## Where Focus shows up

| Surface | When | What you get |
|---|---|---|
| **A — PR comment** | Every PR (GitHub Action) | Full architecture HUD — summary, Mermaid, Danger Zones. Updates in place on new pushes |
| **C — IDE diff** | Before you push (Cursor / VS Code) | Risk rail + edit-shaped ℹ️; **live while typing** (unsaved buffer); Save refresh; SCM Working Tree (right pane); HUD map |
| **C — GitHub diff** | PR review (planned) | Inline pins on **Files changed** — companion to the PR comment |
| ~~**B — git**~~ | — | **Not supported** — no committed `focus-hud.md` |

Same evidence everywhere: parse → graph → `FocusHUD` → renderer (markdown comment, webview, CodeLens, future GitHub annotations).

---

## In Cursor / VS Code (diff-first · surface C)

Risk rail + purpose ℹ️ on changed symbols, plus the full HUD panel — blast radius **in the diff you're editing**.

**What it looks like in the editor** (virtual UI — nothing written to git):

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

| Surface | Where | What |
|---|---|---|
| **Risk rail** | Above `def` / `class` | Implication: `{emoji} {RISK} — {who} — {what goes wrong}`. Quiet when LOW |
| **ℹ️ Purpose** | Above the primary edit (or each distinct outcome) | What this edit does — one per symbol unless hunks truly differ |
| **Trust cues** | Hover highlighted code, or click rail / ℹ️ | *Why trust this* — ≤2 cues (map in HUD). Don’t rely on CodeLens title hover on macOS. |

```bash
./scripts/install-extension.sh
```

(Needs `focus-hud` on PATH — the script installs the editable package too.)

Open the **repo git root**, set `focus.path` if needed, **Reload Window** once, and run **Focus: Audit Local Changes**. After that:

- **Live while typing** — dirty buffers refresh rails after a short debounce (`focus.liveBufferOverlay`, default on). No Save required.
- **Save** still re-audits from disk (`focus.autoAuditOnSave`).

Details: [`extensions/vscode-focus/README.md`](extensions/vscode-focus/README.md).

| Moment | Command | You get |
|---|---|---|
| AI rewrote a shared function | Edit (live) or **Save** / **Focus: Audit Local** | **C** — risk rail + ℹ️ in your working file / diff |
| Big PR in your queue | Focus Action comment | **A** — diagram + Danger Zones on the PR |
| Inherited a module | `focus trace path/to/file.py` | Downstream map for one file |

---

## GitHub Action (surface A · any repo)

Copy [`examples/focus-action.yml`](examples/focus-action.yml) → `.github/workflows/focus.yml`.  
On every PR open/sync, Focus posts (and updates) a HUD **comment** — not a file in the commit.

Details: [`docs/ACTION.md`](docs/ACTION.md). Permissions: `contents: read` + `pull-requests: write` only ([`docs/PRIVACY.md`](docs/PRIVACY.md)).

**Phase 5:** inline annotations on the PR diff (**C** on GitHub) — see [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Getting started (from this repo)

```bash
git clone https://github.com/j0viane/focus.git
cd focus
uv sync
uv run focus scan .
uv run focus trace src/focus/models.py --out focus-hud.md
uv run focus audit --local
```

Unchanged files reuse **`.focus-cache/`** (gitignored). Pass `--no-cache` to force a full re-parse.

Optional: copy [`.focus.toml.example`](.focus.toml.example) → `.focus.toml` to tune `fan_out_threshold` (default **3**).

Requirements: Python 3.12+. Install: **`pip install "focus-hud>=0.3.3"`** (CLI: `focus`). Publish notes: [`docs/PUBLISH.md`](docs/PUBLISH.md).

```bash
uv run pytest
```

---

## Why "Focus"?

The name comes from *Horizon Zero Dawn*. Aloy navigates an inherited world with her **Focus** — an AR device that reveals weak points and danger ahead. A legacy codebase is the same kind of world. This Focus scans it so you change it with intel, not blind faith.

*Horizon Zero Dawn and Aloy belong to Guerrilla Games — no affiliation, just admiration.*

---

## Architecture

```mermaid
flowchart TB
    subgraph scan [Focus Scan]
        TS[AST Index] --> G[Dependency Graph]
        G --> SURF[Surface Detector]
    end

    subgraph preflight [Blast Radius Engine]
        DIFF[Git Diff / Symbol Target] --> SEED[Changed Symbols]
        SEED --> BFS[Reverse BFS]
        BFS --> DZ[Danger Zone Scorer]
    end

    subgraph hud [Focus HUD]
        ES[Executive Summary]
        MAP[Mermaid Map]
        BR[Blast Radius Report]
    end

    scan --> preflight
    preflight --> hud
    hud --> OUT["A: PR comment · C: IDE / GitHub diff"]
```

| Layer | Technology |
|---|---|
| CLI | Python 3.12+ / Typer (`--format markdown\|json`) |
| AST | Python `ast` + Tree-sitter (JS/TS) |
| Graph | NetworkX |
| Diagrams | Mermaid (GitHub + IDE webview) |
| CI | Opt-in GitHub Action — PR comment (A); inline diff (C) planned |
| IDE | VS Code / Cursor — CodeLens + HUD panel (C) |

---

## Commands

| Command | Purpose |
|---|---|
| `focus scan [path]` | Index the repo (Python + JS/TS) |
| `focus trace [file]` | HUD for one file (`--format json` for tools) |
| `focus audit --local` | Working tree vs `main` |
| `focus audit --base <sha>` | PR / branch range |
| `focus version` | Installed version |

---

## Roadmap

Phase 3 **complete**. Phase 4b **shipping** (risk rail + edit-shaped ℹ️ + **live buffer overlay** + Save refresh + SCM Working Tree). Phase 5 **next** (GitHub diff **C**, beside the **A** PR comment). See [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Ethics & privacy

- **Evidence-based** — no LLM inventing edges
- **Privacy-by-design** — respects `.gitignore`; no source to model APIs
- **No surveillance** — structure, not developer identity
- **Opt-in Action** — minimum token scope

Details: [`docs/ETHICS.md`](docs/ETHICS.md) · [`docs/PRIVACY.md`](docs/PRIVACY.md).

---

## Docs

| Doc | Contents |
|---|---|
| [`docs/DEMO.md`](docs/DEMO.md) | Walkthrough + gallery |
| [`docs/LAUNCH.md`](docs/LAUNCH.md) | Product Hunt / Show HN drafts |
| [`docs/ACTION.md`](docs/ACTION.md) | Action install |
| [`docs/HUD.md`](docs/HUD.md) | HUD schema + JSON contract |
| [`docs/ETHICS.md`](docs/ETHICS.md) | Responsible use |
| [`docs/PRIVACY.md`](docs/PRIVACY.md) | Data boundaries |

---

## License

[MIT](LICENSE) © 2026 Joviane Bellegarde.

## Author

[Joviane Bellegarde](https://github.com/j0viane). Feedback welcome via Issues.
