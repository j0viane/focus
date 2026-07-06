# Focus — Stack Decisions (Locked)

Technology choices for Phase 1–3. **Locked at Phase 0 exit** — change only via explicit ADR in Issues.

**Last updated:** July 2026  
**Status:** Locked

---

## Locked stack

| Layer | Choice | Alternatives considered | Why this choice |
|---|---|---|---|
| **Language** | Python 3.12+ | Go, Rust | Tree-sitter ecosystem, NetworkX, interview fluency, fast MVP |
| **CLI** | Typer | Click, argparse | Type hints, auto `--help`, minimal boilerplate |
| **Package manager** | `uv` (primary), pip compatible | poetry, pipenv | Speed; `pyproject.toml` standard |
| **AST** | Tree-sitter + `tree-sitter-python` | libcst, ast module | Multi-language path, incremental parse, query API |
| **Graph** | NetworkX | Custom adjacency dict, igraph | BFS built-in, readable, sufficient for Phase 1 scale |
| **Models** | Pydantic v2 | dataclasses | HUD schema, validation, JSON serialization |
| **Git** | subprocess `git` + `GitPython` (optional) | pygit2 | subprocess sufficient for diff; GitPython if needed for ergonomics |
| **Diagrams** | Mermaid `flowchart` | D2, Graphviz | Native GitHub PR render; LLM-friendly |
| **Testing** | pytest | unittest | Fixture repos, parametrize for trigger tables |
| **Lint / format** | ruff | black + flake8 | Single tool |
| **LLM (Phase 3+)** | Provider-agnostic interface; Claude/GPT-4o first impl | — | Labels only; swappable via env var |
| **GitHub** | Actions + `GITHUB_TOKEN` | GitHub App | Minimal scope for MVP PR comments |

---

## Explicitly not chosen (Phase 1)

| Option | Reason deferred |
|---|---|
| Neo4j / graph DB | In-memory NetworkX enough for CLI + Action runner |
| Language Server Protocol | Heavier; Tree-sitter sufficient for static imports/calls |
| Full points-to analysis | Phase 3+ research; honest limitation in HUD caveat |
| Docker for dev | Optional Phase 2; local `pip install -e .` for Phase 1 |
| React / web UI | CLI + PR comments are the product surface |

---

## Environment variables (`.env.example` target)

| Variable | Required | Phase | Purpose |
|---|---|---|---|
| `FOCUS_LLM_API_KEY` | No | 3+ | LLM label pass (opt-in) |
| `FOCUS_LLM_PROVIDER` | No | 3+ | `openai` \| `anthropic` |
| `FOCUS_LLM_ENABLED` | No | 3+ | Default `false` |
| `GITHUB_TOKEN` | Action only | 3 | Provided by Actions runtime |

---

## Project layout (Phase 1 target)

```
focus/
├── pyproject.toml
├── src/focus/
│   ├── cli.py              # Typer entrypoint
│   ├── scan/               # Tree-sitter index
│   ├── graph/              # NetworkX builder + BFS
│   ├── ingest/             # git diff
│   ├── triggers/           # smart triggers
│   ├── hud/                # render HUD from schema
│   └── models.py           # Pydantic HUD + graph types
├── tests/
│   └── fixtures/glass_box/
└── docs/
```

---

## Related documents

- [`ROADMAP.md`](ROADMAP.md) — week plan
- [`HUD.md`](HUD.md) — output schema
- [`.cursor/rules/focus-engineering.mdc`](../.cursor/rules/focus-engineering.mdc) — constraints
