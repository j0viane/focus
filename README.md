# Focus

**Blast radius you can defend — evidence-only, before you merge.**

Focus answers one question: **what else in this codebase could break because of this change?**

It's an **AR HUD for codebases**: a computed import graph (Python + JS/TS) → Mermaid map + Danger Zones. Same HUD in the CLI and on the PR. No LLM inventing edges.

> **Not** another AI PR summary. **Not** a hop inventory that cries wolf on every file. Focus stays quiet when the change is boring, and loud when you touch a shared hub.

---

## Try in 60 seconds

```bash
pip install focus-hud
# or: uv tool install focus-hud

focus trace path/to/shared_module.py --out focus-hud.md
# open focus-hud.md → Markdown preview for Mermaid

focus audit --local --out focus-hud.md   # working tree vs main — before you push
```

**Demo fixture (no app required):**

```bash
git clone https://github.com/j0viane/focus.git && cd focus
uv sync
uv run focus trace tests/fixtures/glass_box/auth_utils.py \
  --root tests/fixtures/glass_box --out focus-hud.md
```

Gallery + walkthrough: [`docs/DEMO.md`](docs/DEMO.md) · [`docs/assets/`](docs/assets/)

---

## Why this exists

There's a new kind of pressure on developers — and it lands hardest on juniors: walk into a codebase you've never seen, point an AI at it, and ship. The code arrives in seconds. The understanding doesn't.

Focus is for the moment right before you push into a codebase that was there long before you. **What the system looks like, and what your change will actually touch** — with evidence you can defend in review.

| Moment | Command | You get |
|---|---|---|
| AI rewrote a shared function | `focus audit --local` | Blast radius of your working tree vs `main` |
| Big PR in your queue | Focus Action comment | Skim-or-dig: diagram + Danger Zones, or “low impact” |
| Inherited a module | `focus trace path/to/file.py` | Everything that depends on it |

---

## GitHub Action (any repo)

Copy [`examples/focus-action.yml`](examples/focus-action.yml) → `.github/workflows/focus.yml`.  
Details: [`docs/ACTION.md`](docs/ACTION.md). Permissions: `contents: read` + `pull-requests: write` only ([`docs/PRIVACY.md`](docs/PRIVACY.md)).

---

## Already exists? (CodeLayers, Valerian, …)

Editor tools show hop lists while you type. Focus is **pre-merge decision support**: evidence-only topology, Danger Zones + smart triggers, **one HUD** from `audit --local` to the PR comment. Open source, local, no architecture backend required.

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

Requirements: Python 3.12+. Install: **`pip install focus-hud`** (CLI: `focus`). Publish notes: [`docs/PUBLISH.md`](docs/PUBLISH.md).

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
    hud --> OUT[CLI stdout / GitHub PR comment]
```

| Layer | Technology |
|---|---|
| CLI | Python 3.12+ / Typer |
| AST | Python `ast` + Tree-sitter (JS/TS) |
| Graph | NetworkX |
| Diagrams | Mermaid (native on GitHub) |
| CI | Opt-in GitHub Action |

---

## Commands

| Command | Purpose |
|---|---|
| `focus scan [path]` | Index the repo (Python + JS/TS) |
| `focus trace [file]` | HUD for one file |
| `focus audit --local` | Working tree vs `main` |
| `focus audit --base <sha>` | PR / branch range |
| `focus version` | Installed version |

---

## Roadmap

Phase 3 **complete** — CLI + Action + JS/TS + cache + **`focus-hud` on PyPI**.  
Next product candidate: **IDE extension** (parked until scoped). See [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Ethics & privacy

- **Evidence-based** — no LLM inventing edges
- **Privacy-by-design** — respects `.gitignore`; no source to model APIs
- **No surveillance** — structure, not developer identity
- **Opt-in Action** — minimum token scope

| Doc | Contents |
|---|---|
| [`docs/DEMO.md`](docs/DEMO.md) | Walkthrough + gallery |
| [`docs/LAUNCH.md`](docs/LAUNCH.md) | Product Hunt / Show HN drafts |
| [`docs/ACTION.md`](docs/ACTION.md) | Action install |
| [`docs/HUD.md`](docs/HUD.md) | HUD schema |
| [`docs/ETHICS.md`](docs/ETHICS.md) | Responsible use |
| [`docs/PRIVACY.md`](docs/PRIVACY.md) | Data boundaries |

---

## License

[MIT](LICENSE) © 2026 Joviane Bellegarde.

## Author

[Joviane Bellegarde](https://github.com/j0viane). Feedback welcome via Issues.
