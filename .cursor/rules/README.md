# Focus Cursor Rules

Project-specific rules loaded by Cursor when you work in this repo.

| File | Purpose |
|---|---|
| `focus-agent-gates.mdc` | **Hard gates** — short STOP checklist before coding *(alwaysApply)* |
| `focus-pr-test-plan.mdc` | **PR Test plan** — agent runs automatable checkboxes + updates PR body *(alwaysApply)* |
| `focus-project-status.mdc` | **Handoff / memory** — versions, branch, next steps *(alwaysApply; update when pausing)* |
| `focus-project.mdc` | Product context, architecture, tech stack *(alwaysApply; public)* |
| `focus-engineering.mdc` | Non-negotiable engineering constraints *(alwaysApply; public)* |
| `focus-explanation-voice.mdc` | Junior-facing explainer voice — expand acronyms, intent over jargon *(globs only)* |
| `focus.mdc` | Diagnostic engine identity, HUD contract *(symlink → `cursor-rules/focus/`; **@-mention / requestable**)* |

**Teaching / learning:** global `upskilling.mdc` (`alwaysApply`) + `session-start-teach.sh` / `stop-upskill-recap.sh`. No `AGENTS.md`, no per-project mentorship/learning duplicates. Product gates live in `.cursor/rules`.

Global rules (SWE standards, verification gauntlet, communication, owner profile) live in the private **`cursor-rules`** repo, symlinked to `~/.cursor/plugins/local/swe-standards`. Before commit/push, agents must craft/smell-review (`swe-principles.mdc`) and run project checks (`agent-verification-gauntlet.mdc`) — Focus’s surface is typically `.venv/bin/python -m pytest -q` and `.venv/bin/focus audit --local …`.

**Tip:** Open the Focus folder as the Cursor workspace (not parent `Cursor/`) so these project rules attach reliably. Pull `@focus` when you need the identity/HUD contract.

Private hooks live in **`cursor-rules/focus/`** (local symlinks; gitignored here). See `cursor-rules` README.
