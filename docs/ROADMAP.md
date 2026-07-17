# Focus Roadmap

Living document for project progress. Updated as phases complete.

**Last updated:** July 2026  
**Current phase:** Phase 4 **in progress** — IDE + evidence-pack LLM captions shipped opt-in (4c). **Phase 4d pinned:** portable fact ledger for scope captions (not shipped). Phase 3 complete on PyPI.

---

## Product surfaces (agreed)

One computed `FocusHUD` — multiple renderers. **No committed HUD files in git.**

| Surface | What the user sees | In the repo? |
|---|---|---|
| **A — PR comment** | Full HUD markdown (summary + Mermaid + Danger Zones) on every PR | **No** — posted/updated via GitHub Action |
| **C — Inline in the diff** | Risk + hop context on changed / blast-radius files while reviewing | **No** — IDE CodeLens today; GitHub diff annotations in Phase 5 |
| **B — Committed `.md`** | `focus-hud.md` checked into the tree | **Out of scope** — local/CI scratch only; gitignored |

```
pip install focus-hud
        │
        ├─ Before push (IDE)     → C: CodeLens + HUD panel in your working diff
        │
        └─ On PR (GitHub Action) → A: HUD comment (ship now)
                                 → C: inline diff annotations (Phase 5)
```

---

## North star

**Simple but great:** one command (`focus trace auth_utils.py`) that shows real downstream blast radius on a real repo — not a platform with ten half-working language parsers.

| Ship | Defer |
|---|---|
| Python + JS/TS AST + dependency graph | Go, Rust, Java parsers |
| `focus trace` + `focus audit --local` | Cloud-hosted graph store |
| Mermaid HUD in CLI + PR comments | Interactive D2/SVG viewer |
| PR comment (A) + inline diff (C) | Committed `focus-hud.md` in git (B) |
| Smart triggers (no diagram fatigue) | ML-based trigger classifier |
| Evidence-based Danger Zones | Full points-to / data-flow analysis |
| Parse cache | LLM label pass (parked — hallucination risk) |
| PyPI (`focus-hud`) + drop-in Action | Marketplace listing polish |
| CLI `--format json` + IDE CodeLens MVP | GitHub inline diff annotations (Phase 5) |

---

## Phase 0 — Planning *(complete)*

All exit criteria met. See [`DECISIONS.md`](DECISIONS.md) for resolved open questions.

| Item | Status | Notes |
|---|---|---|
| Product definition + HUD output schema | **Done** | [`docs/HUD.md`](HUD.md) |
| Stack confirmation | **Done** | [`docs/STACK.md`](STACK.md) |
| Smart trigger rule table | **Done** | [`docs/TRIGGERS.md`](TRIGGERS.md) |
| Danger Zone scoring rubric | **Done** | HUD.md + ETHICS + `focus.mdc` |
| Privacy model | **Done** | [`docs/PRIVACY.md`](PRIVACY.md) |
| Ethics model | **Done** | [`docs/ETHICS.md`](ETHICS.md) |
| Testing pyramid | **Done** | [`docs/TESTING.md`](TESTING.md) |
| Golden fixture spec | **Done** | `tests/fixtures/glass_box/` in TESTING.md |
| Learning + mentorship rules | **Done** | `cursor-rules/focus/` |
| Public README + roadmap | **Done** | |

### Phase 0 exit criteria

- [x] Trigger rules documented (`docs/TRIGGERS.md`)
- [x] Privacy + ethics principles documented
- [x] Explicit "won't build" list agreed
- [x] HUD schema frozen (`docs/HUD.md`)
- [x] Stack confirmation locked (`docs/STACK.md`)
- [x] Phase 1 step plan agreed (below)

---

## Phase 1 — Focus Scan (Python only) *(complete)*

**Goal:** Parse a Python repo and emit a dependency map for one file.

| Step | Deliverable | Tests added | Explain-back | Status |
|---|---|---|---|---|
| **1** | `pyproject.toml`, Typer CLI, `focus scan` walks repo + respects `.gitignore` | `glass_box/` fixture, pytest harness, smoke tests | Parse pipeline diagram | ✅ |
| **2** | Python facts: defs, imports, call sites → in-memory index | `test_parser.py` — parametrize import/def cases | What AST nodes we extract | ✅ |
| **3** | NetworkX graph + `focus trace [file]` → text HUD (no Mermaid yet) | `test_graph.py`, `test_triggers.py`, parse → graph integration | Reverse edges, downstream list | ✅ |
| **4** | Mermaid renderer + HUD output | `test_hud_golden.py`, Mermaid validator, E2E CLI subprocess | Full HUD walkthrough | ✅ |

**Parser note (post–Phase 3):** Python extraction uses the stdlib **`ast`** module (Tree-sitter Python was dropped after real-repo segfaults). JS/TS still use Tree-sitter.

**Testing principle:** fixture and pytest land at Step 1; each step adds tests **with** the feature — see [`TESTING.md`](TESTING.md).

**Constraints:**

- Full-repo parse (no diff-only blindspots)
- LLM optional in Phase 1 — labels can be static; topology must be computed
- One language until graph pipeline is proven

---

## Phase 2 — Blast Radius Engine *(complete)*

| Feature | Purpose | Status |
|---|---|---|
| `focus audit --local` | Git diff → changed files → reverse BFS → HUD | ✅ |
| Danger Zone scorer | Flag API routes, schemas, high fan-out nodes | ✅ path + fan-out + `.focus.toml` |
| Smart triggers | Skip diagram for docs/comments/test/isolated | ✅ |
| Focus HUD v1 | Executive summary + Mermaid + bulleted blast radius | ✅ |
| IDE preview (`--out`) | Write HUD markdown for editor Mermaid preview | ✅ |
| Symbol-aware diff | Report touched defs; comments-only → pass-through | ✅ |

---

## Phase 3 — GitHub Action + multi-language *(complete)*

| Feature | Purpose | Status |
|---|---|---|
| GitHub Action | `focus audit` on PR open/sync → PR comment | ✅ |
| PR-range audit | `focus audit --base <sha>` uses `base...HEAD` | ✅ |
| Blast-radius signal polish | Quieter Danger Zones; reasons name real importers | ✅ |
| JS/TS Tree-sitter grammar | Web repo support | ✅ |
| Parse cache | File-hash keyed AST cache for speed | ✅ |
| PyPI publish (`focus-hud`) | `pip install focus-hud` — CLI remains `focus` | ✅ 0.1.0 |
| Drop-in Action for any repo | [`examples/focus-action.yml`](../examples/focus-action.yml) | ✅ |

LLM label pass was **removed from Phase 3** and parked (see below): Focus ships evidence-only HUDs so we never add model-generated copy that can hallucinate.

---

## Phase 4 — IDE (diff-first) *(in progress)*

**Goal:** Surface **C** locally — blast-radius context *in the diff you're editing*, not only in a side panel.

| Feature | Purpose | Status |
|---|---|---|
| `focus … --format json` | Machine-readable `FocusHUD` for tools | ✅ 0.2.0 |
| VS Code / Cursor extension | Install via VSIX or `scripts/install-extension.sh` | ✅ MVP |
| CodeLens on changed / blast-radius files | Risk + downstream count at top of file | ✅ MVP |
| HUD webview panel | Same Mermaid + Danger Zones as CLI / PR comment | ✅ MVP |
| CodeLens on changed **lines/symbols** | True inline diff context (not just file header) | ✅ 0.2.1 |
| Gutter hop markers + “why this edge” | Click claim → import evidence | 🔄 MVP (gutter + showWhy; import jump pending) |
| Inline symbol explanations | Stacked CodeLens `↳` captions on changed defs | ✅ branch |
| `focus explain --why` | CLI evidence trail (proven vs heuristic) per caption | ✅ branch |
| Marketplace publish | Easy install for strangers | Pending |

---

## Phase 4b — Explanation depth *(in progress)*

**Goal:** Close the known gaps in deterministic explanations — still **no LLM** for dependency edges or captions. Guard **Return on Attention (ROA)**: every word Focus asks a human to read must earn its cost.

| Limitation today | Planned improvement | Status |
|---|---|---|
| **Hunk copy names enclosing `def`** | Hybrid: structural cues → proven `CallSite` → text heuristics; skip plumbing callees | ✅ slice 1 |
| **Implication rail** | `{emoji} {RISK} — {who} — {what goes wrong}`; quiet when LOW | ✅ slice 2 |
| **CodeLens layout** | Risk rail on `def` + one ℹ️ unless hunks differ; hover = evidence | ✅ slices 3–4 |
| **File-level blast radius** | Symbol-level downstream (who calls *this* def, not just the file) | Planned |
| **Static-only graph** | Best-effort dynamic import / string-literal hints where parseable | Explore |
| **Heuristic captions** when no docstring | JSDoc/TSDoc extraction for JS/TS; Typer `@app.command` metadata for CLI | Planned |
| **Evidence in IDE** | Hover = *why trust this* only (≤2 cues); no restating rail/ℹ️; importers collapsed → HUD | ✅ ROA slim |
| **Verbose / low-ROA copy** | Hard caps: max chars for ℹ️ / summary; one idea per lens; no restating the header | 🔄 hover done; caps continue |
| **PR comment inventory dump** | Cap **Your changes** at 8 + overflow; cap Also affected / Not pulled in at 8; prefer short detail over long explanation | ✅ focus-hud 0.3.4 |
| **Tiny diff, huge output** | Stronger triggers: tiny + low blast radius → pass-through or *tiny* HUD (see [`TRIGGERS.md`](TRIGGERS.md)) | Planned (ROA) |
| **Auto-refresh on save** | Quiet re-audit after saving a source file; CodeLens/gutters update in place (`focus.autoAuditOnSave`) | ✅ extension 0.5.1 |
| **SCM Working Tree CodeLens** | Same risk rail + ℹ️ on the **modified** side of local side-by-side diffs (`diffEditor.codeLens`) and the open file (`editor.codeLens`) | ✅ |
| **Edit-shaped captions** | Deterministic ℹ️ from the edit: blank counts, imports, calls, returns, assigns — not static slogans | ✅ focus-hud 0.3.2 / extension 0.5.2 |
| **Expression-slot captions** | Return/assign ℹ️ include a clipped expression when readable; weak/`None`/code-soup yield to purpose (LLM labeler still planned) | ✅ focus-hud 0.3.3 |
| **Live-as-you-type** | Debounced refresh from the **unsaved buffer** (not only disk/git) — `--overlay-file` + `focus.liveBufferOverlay` | ✅ focus-hud 0.3.3 / extension 0.5.3 |
| **Evidence-pack LLM captions** | Opt-in labeler for **all** ℹ️ (incl. blank-line); pack-constrained; never invents edges; never on live overlay | ✅ focus-hud 0.3.5 / extension 0.5.4 |

**Pinned UX (IDE):** Rails and ℹ️ refresh while editing via buffer overlay (`focus.liveBufferOverlay`, default on). Save→auto-audit remains as a disk sync. Marketplace polish can follow once this feels instant in dogfood.

**Trust model:** every caption labels evidence as **proven** (parse/graph/diff) or **heuristic** (name/path rules / optional `llm_label`). `focus explain --why` shows the cite list today; IDE surfacing is next.

**Slice 1 concept:** a *call site* is where code invokes a name (`foo()`). Parser already records these. Hybrid order: structural cues (`kind=`) first, then proven overlapping calls, then weaker text heuristics.

**ROA (product rule, not a separate product):** Focus must never become the “1-line change + 1,430-character description” anti-pattern. Prefer silence or one sentence over filler. Virtual UI only — never write explainers into the repo.

---

## Phase 4c — Evidence-pack caption labeler *(shipped opt-in)*

**Goal:** When caption labeling is opt-in, an LLM may **relabel every ℹ️ from a `CaptionEvidencePack`** Focus already built — including blank-line captions — never invent topology. Fail-closed validate keeps the deterministic caption on reject.

| Knob | Default |
|---|---|
| `FOCUS_LLM_ENABLED` / `.focus.toml [llm] captions` | off |
| `FOCUS_LLM_PROVIDER` | `openai` (cloud) or **`ollama`** (no-key local dogfood) |
| `focus audit --llm-captions` | dogfood / CI force-on for one run |
| Extension `focus.llmCaptions` | false (explicit **Audit Local**: deterministic rails first, LLM captions in background — never autosave / overlay) |

**Dogfood checklist (all captions when enabled, before leaving on by default):**

1. Unit grounding tests green (`tests/test_llm_labeler.py`).
2. **Preferred no-key path:** install [Ollama](https://ollama.com), `ollama pull qwen2.5:7b`, local `.env` (never commit):
   ```
   FOCUS_LLM_ENABLED=true
   FOCUS_LLM_PROVIDER=ollama
   FOCUS_LLM_MODEL=qwen2.5:7b
   ```
   Or cloud: `FOCUS_LLM_API_KEY` + `openai`/`anthropic`. Keep default off in committed configs.
3. One run: `focus audit --local --llm-captions` (no overlay). Every changed-symbol caption is a candidate; expect more LLM calls / latency than weak-only.
4. For each caption that gained `llm_label` evidence, score: invent entity? invent behavior not in pack? better than silence/deterministic?
5. Accept only if **zero** topology invent and no ungrounded scope/entity slips past validate; otherwise leave default off.

---

## Phase 4d — Portable fact ledger for captions *(pinned)*

**Status:** Design pin only (2026-07-16). Not implemented.

**Problem dogfood surfaced:** Measured ℹ️ often names *edit shape* (`Updates \`weak_hit\` here.`, orphan “outside a function”) without *scope* (what changed in the target code, who uses it). An LLM can invent fluent scope; Focus must not. CEOs’ “AI replaces judgment” narrative does not license ungrounded captions.

**Constraint (non-negotiable):** The ledger is built from the **target codebase** Focus is analyzing — AST + diff + graph for *that* tree. No Focus-specific symbol dictionaries (e.g. special-casing `_WEAK_MARKERS`). The same algorithm must work on a stranger’s repo.

**Direction (ship order when we pick this up):**

1. **Generic edit facts** — literal adds/removes on names, assignment + clipped RHS, return expr, imports; same-file “name `X` read in `f`”.
2. **Attach who** — importers / local callers from the graph when known.
3. **Template captions** from those facts (accurate by construction).
4. **Opt-in LLM labeler** only after 1–3 dogfood — polish English from the richer pack; fail-closed validate unchanged.
5. **First-class `EditFact` / `UseFact` / `ImpactFact` models** if the pack gets messy (defer).

**Success check:** On any repo, a module-level constant edit reads as defendable scope — not “Edited outside a changed function…” and not insider product jokes.

---

## Phase 5 — GitHub inline diff *(next bet after 0.2.0)*

**Goal:** Surface **C** on GitHub — pins on the PR **Files changed** tab, alongside existing **A** PR comment.

| Feature | Purpose | Status |
|---|---|---|
| Per-file review comments | Danger Zone / hop count on changed files in blast radius | Planned |
| Check-run annotations (optional) | File-level signals in Checks UI | Explore |
| Same `FocusHUD` as Action | Reuse `focus audit --format json`; A comment stays the overview | Planned |

**A** (PR comment block) ships now via [`examples/focus-action.yml`](../examples/focus-action.yml). **C** on GitHub layers on top — not a replacement.

---

## Explicitly out of scope (for now)

- **Committed HUD markdown in git** (`focus-hud.md` as a tracked artifact) — use PR comment (A) + inline diff (C) instead
- Diff-only analysis without full-repo graph context
- LLM inventing dependency edges / Mermaid nodes not in the computed graph
- **LLM free-summarizing hunks without an evidence pack** — v1 labeler is pack-constrained (Phase 4c); free prose remains won't-build
- Blocking PR merges or developer quizzes
- Developer surveillance, blame metrics, or performance scoring
- Interactive hosted code maps (CodeSee-style SaaS)
- PlantUML / D2 as primary output (Mermaid first; SVG fallback later)
- Sending full repository source to LLM APIs
- Covert repo analysis without workflow opt-in

Full ethics list: [`docs/ETHICS.md`](ETHICS.md)

---

## Parking lot — future ideas (unscoped, not promised)

- **Evidence-pack caption labeler (Phase 4c):** shipped opt-in in focus-hud 0.3.5 — labels all ℹ️ from capped edit packs when enabled; never invents edges. Free-form / topology LLM remains parked.
- **IDE extension (Phase 4 — deepen C):** symbol-level CodeLens, gutter hop colors, always-on watch, auditable “why this edge” deep links.
- **GitHub inline diff (Phase 5):** review comments / annotations on PR diff — companion to PR comment (A).
- **More languages (Go / Rust / Java):** adoption breadth only — not the differentiator. Revisit when a real user is blocked without them.
- **Auditable “why this edge”:** click from HUD claim → import evidence (line). Trust theater → trust proof. **`focus explain --why`** ships on the inline-explanations branch; IDE deep-link next.

---

## Updates

- **This file** — phase status and scope
- **[`DEMO.md`](DEMO.md)** — walkthrough + gallery assets
- **[`LAUNCH.md`](LAUNCH.md)** — Product Hunt / Show HN copy (optional)
- **[`PUBLISH.md`](PUBLISH.md)** — PyPI Trusted Publishing
- **Issues** — architecture decisions and parser edge cases

Questions or blast-radius heuristics? [Open an issue](https://github.com/j0viane/focus/issues/new).
