# Focus Roadmap

Living document for project progress. Updated as phases complete.

**Last updated:** July 2026  
**Current phase:** Phase 0 — planning

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

## Phase 0 — Planning *(in progress)*

No application code until these are locked.

| Item | Status | Notes |
|---|---|---|
| Product definition + HUD output schema | **Done** | README + this doc |
| Stack confirmation (Python, Tree-sitter, NetworkX, Mermaid, Typer) | Pending | |
| Smart trigger rule table (path + AST + blast radius threshold) | **Done** | [`docs/TRIGGERS.md`](TRIGGERS.md) |
| Danger Zone scoring rubric | **Done** | In `cursor-rules/focus/focus.mdc` + ETHICS |
| Privacy model | **Done** | [`docs/PRIVACY.md`](PRIVACY.md) |
| Ethics model | **Done** | [`docs/ETHICS.md`](ETHICS.md) |
| Testing pyramid | **Done** | [`docs/TESTING.md`](TESTING.md) |
| First target repo for golden tests | **Done** | `tests/fixtures/glass_box/` spec in TESTING.md |
| Public README + roadmap | **Done** | |
| Engineering + learning rules in repo | **Done** | `.cursor/rules/` + `cursor-rules/focus/` |

### Phase 0 exit criteria

- [x] Trigger rules documented (`docs/TRIGGERS.md`)
- [x] Privacy + ethics principles documented (`docs/PRIVACY.md`, `docs/ETHICS.md`)
- [x] Explicit "won't build" list agreed (ETHICS + ROADMAP below)
- [ ] HUD schema frozen (Executive Summary + Mermaid + Blast Radius blocks)
- [ ] Stack confirmation locked
- [ ] Phase 1 week plan agreed

---

## Phase 1 — Focus Scan (Python only)

**Goal:** Parse a Python repo and emit a dependency map for one file.

| Week | Deliverable |
|---|---|
| **1** | Project scaffold: `pyproject.toml`, Typer CLI shell, `focus scan` walks repo |
| **2** | Tree-sitter Python parser: extract defs, imports, call sites |
| **3** | NetworkX dependency graph + `focus trace [file]` HUD (text table first) |
| **4** | Mermaid renderer + golden test on fixture repo (`auth → billing → dashboard`) |

**Constraints:**

- Full-repo parse (no diff-only blindspots)
- LLM optional in Phase 1 — labels can be static; topology must be computed
- One language until graph pipeline is proven

---

## Phase 2 — Blast Radius Engine

| Feature | Purpose |
|---|---|
| `focus audit --local` | Git diff → changed symbols → reverse BFS |
| Danger Zone scorer | Flag API routes, schemas, high fan-out nodes |
| Smart triggers | Skip diagram for markdown/CSS/isolated utils |
| Focus HUD v1 | Executive summary + Mermaid + bulleted blast radius |

---

## Phase 3 — GitHub Action + multi-language

| Feature | Purpose |
|---|---|
| GitHub Action | `focus audit` on PR open/sync → PR comment |
| JS/TS Tree-sitter grammar | Web repo support |
| LLM label pass | Business-meaningful node names from graph JSON |
| Parse cache | File-hash keyed AST cache for speed |

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

## Updates

- **This file** — phase status and scope
- **Issues** — architecture decisions and parser edge cases

Questions or blast-radius heuristics? [Open an issue](https://github.com/j0viane/focus/issues/new).
