# Focus Roadmap

Living document for project progress. Updated as phases complete.

**Last updated:** July 2026  
**Current phase:** Phase 3 — JS/TS Tree-sitter next; parse cache then LLM labels; IDE still parked

---

## North star

**Simple but great:** one command (`focus trace auth_utils.py`) that shows real downstream blast radius on a real repo — not a platform with ten half-working language parsers.

| Ship | Defer |
|---|---|
| Python-only AST + dependency graph | Go, Rust, Java parsers |
| `focus trace` + `focus audit --local` | Cloud-hosted graph store |
| Mermaid HUD in CLI + PR comments | Interactive D2/SVG viewer |
| Smart triggers (no diagram fatigue) | ML-based trigger classifier |
| Evidence-based Danger Zones | Full points-to / data-flow analysis |

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

## Phase 1 — Focus Scan (Python only)

**Goal:** Parse a Python repo and emit a dependency map for one file.

| Step | Deliverable | Tests added | Explain-back | Status |
|---|---|---|---|---|
| **1** | `pyproject.toml`, Typer CLI, `focus scan` walks repo + respects `.gitignore` | `glass_box/` fixture, pytest harness, smoke tests | Parse pipeline diagram | ✅ |
| **2** | Tree-sitter Python: defs, imports, call sites → in-memory index | `test_parser.py` — parametrize import/def cases | What AST nodes we extract | ✅ |
| **3** | NetworkX graph + `focus trace [file]` → text HUD (no Mermaid yet) | `test_graph.py`, `test_triggers.py`, parse → graph integration | Reverse edges, downstream list | ✅ |
| **4** | Mermaid renderer + HUD output | `test_hud_golden.py`, Mermaid validator, E2E CLI subprocess | Full HUD walkthrough | ✅ |

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

## Phase 3 — GitHub Action + multi-language

| Feature | Purpose | Status |
|---|---|---|
| GitHub Action | `focus audit` on PR open/sync → PR comment | ✅ |
| PR-range audit | `focus audit --base <sha>` uses `base...HEAD` | ✅ |
| Blast-radius signal polish | Quieter Danger Zones; reasons name real importers | ✅ |
| JS/TS Tree-sitter grammar | Web repo support | 🟡 next |
| LLM label pass | Business-meaningful node names from graph JSON | ⬜ after JS/TS |
| Parse cache | File-hash keyed AST cache for speed | ⬜ after JS/TS |

---

## Explicitly out of scope (for now)

- Diff-only analysis without full-repo graph context
- LLM inventing dependency edges not in the computed graph
- Blocking PR merges or developer quizzes
- Developer surveillance, blame metrics, or performance scoring
- Interactive hosted code maps (CodeSee-style SaaS)
- PlantUML / D2 as primary output (Mermaid first; SVG fallback later)
- Sending full repository source to LLM APIs
- Covert repo analysis without workflow opt-in

Full ethics list: [`docs/ETHICS.md`](ETHICS.md)

---

## Parking lot — future ideas (unscoped, not promised)

- **IDE extension (Phase 4+ candidate):** show the Focus HUD inline in the editor, next to the code being changed — a third surface after CLI (Phase 1–2) and PR comments (Phase 3). Same engine, same computed graph; only the display changes. Deliberately unscoped until the CLI + Action prove the core loop.

---

## Updates

- **This file** — phase status and scope
- **Issues** — architecture decisions and parser edge cases

Questions or blast-radius heuristics? [Open an issue](https://github.com/j0viane/focus/issues/new).
