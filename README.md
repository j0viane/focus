# Focus

Focus is an **architectural diagnostic engine** — an "AR HUD for codebases." It transforms opaque legacy repositories into transparent **Glass Box** environments so developers can see the logic strings of a system before they make a change.

> **Status:** Phase 1 in progress — CLI scaffold landed; parser, graph, and HUD are being built in the open. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Why this exists

AI coding assistants generate massive pull requests in seconds, but those PRs wait **4.6× longer** to be reviewed. A standard text diff does not show *blast radius* — who imports this function, which API routes break, which schemas drift.

Existing tools dump 1,000-word summaries onto PRs. Focus replaces text walls with **evidence-based visual clarity**:

- **Focus Scan** — Tree-sitter parses the full repo and maps structural nodes (imports, calls, routes, schemas).
- **Blast Radius Engine** — Simulates ripple effects of a proposed change; highlights Danger Zones before merge.
- **Focus HUD** — Executive summary + Mermaid dependency map + bulleted blast radius report.

Passive enablement only: no blocking commits, no quizzing developers.

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
| CLI | Python 3.12+ / Typer or Click |
| AST parsing | Tree-sitter (multi-language grammars) |
| Graph | NetworkX (dependency + blast radius traversal) |
| Diagrams | Mermaid.js (native GitHub rendering) |
| LLM | Off by default (`FOCUS_LLM_ENABLED=false`); optional labels only — topology is computed, not hallucinated |
| GitHub integration | GitHub Action on PR open/sync |

**Core pipeline:** Full-repo Tree-sitter index → dependency graph → diff/symbol seeds → reverse BFS blast radius → smart triggers (diagram vs summary) → Focus HUD.

See [`.cursor/rules/focus-engineering.mdc`](.cursor/rules/focus-engineering.mdc) for non-negotiable engineering constraints.

---

## Commands (planned)

| Command | Purpose |
|---|---|
| `focus scan [path]` | Full-repo AST index + dependency map |
| `focus trace [file]` | Trace what a file/symbol connects to |
| `focus audit [pr\|branch]` | Pre-merge blast radius for a PR or branch diff |
| `focus audit --local` | Pre-flight against working tree vs `main` |

---

## Roadmap (summary)

| Phase | Goal |
|---|---|
| **0** *(complete)* | Stack decisions, HUD schema, trigger rules, learning docs |
| **1** *(now)* | Python CLI: `focus scan` + `focus trace` on one language (Python) |
| **2** | Blast radius engine + `focus audit --local` + Mermaid HUD |
| **3** | JS/TS parsers, smart triggers, GitHub Action |

Full detail: [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## Getting started

> Phase 1 is in progress. The CLI installs and runs; `scan` and `trace` land as Phase 1 progresses — until then `focus scan` exits with "not implemented" rather than pretending to work.

```bash
git clone https://github.com/j0viane/focus.git
cd focus
uv sync            # or: pip install -e .
uv run focus --help
uv run focus version
```

Requirements: Python 3.12+, [`uv`](https://docs.astral.sh/uv/) (or `pip`). Tree-sitter grammars arrive with the parser in Phase 1.

Run the tests:

```bash
uv run pytest
```

---

## Ethics & privacy

Focus is **passive enablement** — it informs reviewers; it never blocks merges or quizzes developers.

- **Evidence-based** — graph topology is computed; the LLM labels only, never invents edges
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
