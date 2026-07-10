# Focus

Focus answers one question before you merge: **what else in this codebase could break because of this change?**

It's an **AR HUD for codebases**: it maps how the pieces of a repository connect — imports, calls, API routes, schemas — and shows the blast radius of a change before it merges.

> **Status:** Phase 2 in progress — `focus audit --local` audits your working tree vs `main`. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Why this exists

There's a new kind of pressure on developers — and it lands hardest on juniors: walk into a codebase you've never seen, point an AI at it, and ship. Developers used to build a mental map of a system by debugging it the old-fashioned way: tracing calls, breaking things, fixing them. That process has been compressed into a prompt. The code now arrives in seconds. The understanding doesn't.

Focus exists for the moment right before you commit and push to a codebase that was there long before you. It shows two things, with evidence: **what the system looks like right now, and what your proposed change will actually touch** — who imports this function, which API routes break, which schemas drift. That's the difference between "the AI wrote it and it seems fine" and "I checked — here's the map." Confidence you can defend in review, whether you're a junior shipping your first AI-assisted PR or a senior reviewing your tenth one today. And the stakes are real: catching a missed dependency before merge costs minutes; catching it after costs the week.

Existing tools dump 1,000-word summaries onto PRs. Focus replaces text walls with **evidence-based visual clarity**:

- **Focus Scan** — Tree-sitter parses the full repo and maps structural nodes (imports, calls, routes, schemas).
- **Blast Radius Engine** — Simulates ripple effects of a proposed change; highlights Danger Zones before merge.
- **Focus HUD** — Executive summary + Mermaid dependency map + bulleted blast radius report.

---

## When you'd use it

| The moment | What you'd do | What you get |
|---|---|---|
| Your AI assistant just rewrote a shared function | `focus audit --local` before you push | The blast radius of your working tree vs `main` — before anyone else sees the PR |
| An 800-line AI-generated PR lands in your review queue | Read the Focus HUD on the PR | A skim-or-dig decision in one glance: diagram + Danger Zones, or a one-line "low impact" |
| You inherited a module and need to change it | `focus trace path/to/file.py` | Everything that depends on that file, before you touch it |
| You're renaming or moving a shared utility | `focus trace`, then `focus audit --local` | Every consumer of that symbol, so the refactor surprises no one |
| A migration or API route changes | `focus audit` on the branch | Which parts of the app actually reach that schema or endpoint |

Commands land per the roadmap below — `scan` works today; `trace` and `audit` are Phase 1–2; the PR comment is Phase 3.

---

## Getting started

> Phase 1 core loop is in: `focus scan` indexes a repo, `focus trace` prints a Focus HUD (summary + Mermaid + blast radius). `focus audit` and smart triggers land in Phase 2.

```bash
git clone https://github.com/j0viane/focus.git
cd focus
uv sync            # or: pip install -e .
uv run focus --help
uv run focus scan .
uv run focus trace src/focus/models.py
uv run focus audit --local
```

`focus audit --local` diffs your working tree against `main` and prints a Focus HUD for the blast radius of those changes.

Requirements: Python 3.12+, [`uv`](https://docs.astral.sh/uv/) (or `pip`). Tree-sitter grammars arrive with the parser in Phase 1.

Run the tests:

```bash
uv run pytest
```

---

## Why "Focus"?

The name comes from *Horizon Zero Dawn*. The game's world was built by a civilization that is long gone, and it runs on machines no one alive fully understands. Aloy can navigate it because of her **Focus** — a small AR device that scans that inherited world and reveals what the naked eye can't: machine weak points, hidden paths, danger ahead. Intel first, decisions second.

A legacy codebase is the same kind of world — built by people who have moved on, full of machinery nobody fully understands anymore. This Focus scans it and surfaces what a raw diff can't, so you make the change with intel instead of walking in blind.

In other words: Aloy is the junior engineer handed a legacy codebase. The Focus is how she reads it. And fittingly, in the game's lore, the Focus was originally designed to educate the next generation about the world they inherited.

*Horizon Zero Dawn and Aloy belong to Guerrilla Games — no affiliation, just admiration.*

---

## Architecture

```mermaid
flowchart TB
    subgraph scan [Focus Scan]
        TS[Tree-sitter AST Index] --> G[Dependency Graph]
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
    hud --> OUT[CLI stdout / GitHub PR comment]
```

| Layer | Technology |
|---|---|
| CLI | Python 3.12+ / Typer |
| AST parsing | Tree-sitter (multi-language grammars) |
| Graph | NetworkX (dependency + blast radius traversal) |
| Diagrams | Mermaid.js (native GitHub rendering) |
| LLM | Off by default (`FOCUS_LLM_ENABLED=false`); optional labels only — topology is computed, not hallucinated |
| GitHub integration | GitHub Action on PR open/sync |

**Core pipeline:** Full-repo Tree-sitter index → dependency graph → diff/symbol seeds → reverse BFS blast radius → smart triggers (diagram vs summary) → Focus HUD.

See [`.cursor/rules/focus-engineering.mdc`](.cursor/rules/focus-engineering.mdc) for non-negotiable engineering constraints.

---

## Commands

| Command | Purpose | Status |
|---|---|---|
| `focus scan [path]` | Full-repo AST index + dependency map | 🟡 Works today: indexes imports, definitions, and calls per file; dependency map lands next |
| `focus trace [file]` | Focus HUD for a file: summary, Mermaid map, blast radius | ✅ Works today (text + Mermaid); smart triggers land in Phase 2 |
| `focus audit [pr\|branch]` | Pre-merge blast radius for a PR or branch diff | ⬜ Phase 2 |
| `focus audit --local` | Pre-flight against working tree vs `main` | 🟡 Works on this branch — git diff → blast radius HUD |
| `focus version` | Print the installed version | ✅ |

---

## Roadmap (summary)

| Phase | Goal |
|---|---|
| **0** *(complete)* | Stack decisions, HUD schema, trigger rules, learning docs |
| **1** *(complete)* | Python CLI: `focus scan` + `focus trace` with Mermaid HUD |
| **2** | `focus audit --local`, Danger Zone polish, smart triggers |
| **3** | JS/TS parsers, GitHub Action, optional LLM labels |

Full detail: [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## Ethics & privacy

- **Evidence-based** — graph topology is computed; an LLM (when enabled) only labels nodes, it never invents edges
- **Privacy-by-design** — respects `.gitignore`; secrets excluded; LLM receives structured graph JSON, not full source (Phase 3+)
- **No surveillance** — analyzes code structure, not developer identity or velocity
- **Opt-in GitHub Action** — minimum token scope; repos choose to install

| Document | Contents |
|---|---|
| [`docs/HUD.md`](docs/HUD.md) | Frozen HUD output schema (source of truth) |
| [`docs/STACK.md`](docs/STACK.md) | Locked technology choices |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Phase 0 resolved questions |
| [`docs/ETHICS.md`](docs/ETHICS.md) | Responsible use, anti-weaponization, LLM ethics |
| [`docs/PRIVACY.md`](docs/PRIVACY.md) | Data boundaries, secrets, LLM payloads, Action permissions |
| [`docs/TRIGGERS.md`](docs/TRIGGERS.md) | Smart triggers — diagram vs pass-through |
| [`docs/TESTING.md`](docs/TESTING.md) | Testing pyramid, golden fixtures, CI constraints |

---

## License

[MIT](LICENSE)

---

## Author

Built by [Joviane Bellegarde](https://github.com/j0viane). Feedback and architecture review tips welcome via Issues.
