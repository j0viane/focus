# Focus — Ethics & Responsible Use

Living document. Defines how Focus should behave toward developers, teams, and the codebases it analyzes.

**Last updated:** July 2026  
**Status:** Phase 0 — principles locked before application code

---

## Purpose

Focus exists to **reduce merge fear and review friction**, not to police developers, score individuals, or replace human judgment. Every design choice should increase **Confidence to Merge** through evidence — not through authority or surveillance.

---

## Core principles

### 1. Passive enablement only

Focus **informs**; it never **blocks**.

| Allowed | Not allowed |
|---|---|
| PR comments with HUD output | Required checks that fail CI |
| Local CLI pre-flight (`focus audit --local`) | Quizzes, attestations, or merge gates |
| Optional GitHub Action (repo opts in) | Org-wide mandatory deployment without consent |

Teams choose to install Focus. Focus does not choose for them.

### 2. Evidence over authority

- Dependency edges and blast radius are **computed** from static analysis — not asserted by an LLM.
- The LLM may label nodes and summarize impact; it **must not invent** topology.
- When evidence is incomplete (dynamic imports, runtime reflection, macros), Focus **states uncertainty** rather than implying completeness.

False confidence is worse than no diagram.

### 3. No developer surveillance

Focus analyzes **code structure**, not **developer behavior**.

| In scope | Out of scope |
|---|---|
| Files, symbols, imports, routes, schemas | Who wrote a line, commit velocity, individual metrics |
| Blast radius of a proposed change | Blame assignment or performance scoring |
| Architectural coupling signals | Productivity surveillance or ranking developers |

Output is attached to **PRs and paths**, not people.

### 4. Transparent limitations

Focus must communicate what static analysis cannot see:

- Runtime dependency injection
- Dynamic `import()` / `eval` / string-based dispatch
- Cross-repo boundaries (monorepo workspaces excepted when configured)
- Environment-specific config not in the repository

The HUD should include a brief **confidence caveat** when known blindspots apply — not bury them in footnotes.

### 5. Org consent for GitHub integration

The GitHub Action requires explicit repository configuration (`focus.yml` or workflow opt-in). Focus:

- Uses **minimum token scope** (`pull-requests: write`, `contents: read`)
- Posts only to PRs in repos where it is installed
- Does not exfiltrate repository contents to third parties beyond configured LLM API calls (see [`PRIVACY.md`](PRIVACY.md))

### 6. Anti-weaponization

Focus output must not be repurposed as:

- Individual performance review input
- "Risk scores" tied to developers
- Automated merge denial without human review

Documentation and marketing should describe Focus as a **navigation aid**, not an enforcement layer.

---

## LLM use ethics

When the LLM label pass is enabled (Phase 3+):

| Rule | Rationale |
|---|---|
| Send `CaptionEvidencePack` only (slots + capped edit lines) — not full source files or the full graph | Minimize exposure; reduce hallucination surface |
| No training opt-out respected per provider policy | User code must not become vendor training data without consent |
| Validated output only — invalid Mermaid falls back to bullet list | Never post broken or fabricated diagrams |
| Human-readable summary ≤ 2 sentences | Avoid cognitive overload Focus was built to eliminate |

---

## Explicitly won't build

- Merge-blocking or required-status checks
- Developer identity tracking or contribution analytics
- "AI confidence score" without cited graph evidence
- Selling or sharing parsed repository data to third parties
- Covert analysis of repos without workflow installation
- Features designed for management surveillance dashboards

---

## Resolved decisions (Phase 0)

See [`DECISIONS.md`](DECISIONS.md) for full log. Summary:

- **HUD caveat:** frozen default in [`HUD.md`](HUD.md) Block 4
- **LLM labels:** parked — not building for now (see [`ROADMAP.md`](ROADMAP.md))
- **Fixtures:** MIT, committed under `tests/fixtures/glass_box/`

---

## Related documents

- [`PRIVACY.md`](PRIVACY.md) — data handling, secrets, LLM payloads
- [`TRIGGERS.md`](TRIGGERS.md) — when Focus generates diagrams vs summaries
- [`.cursor/rules/focus-engineering.mdc`](../.cursor/rules/focus-engineering.mdc) — engineering constraints

Questions? [Open an issue](https://github.com/j0viane/focus/issues/new).
