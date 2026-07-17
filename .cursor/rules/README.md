# Focus Cursor Rules

Project-specific rules loaded by Cursor when you work in this repo.

| File | Purpose |
|---|---|
| `focus-agent-gates.mdc` | **Hard gates** — short STOP checklist before coding *(alwaysApply)* |
| `focus-project-status.mdc` | **Handoff / memory** — versions, branch, next steps *(alwaysApply; update when pausing)* |
| `focus-project.mdc` | Product context, architecture, tech stack *(alwaysApply; public)* |
| `focus-engineering.mdc` | Non-negotiable engineering constraints *(alwaysApply; public)* |
| `focus-explanation-voice.mdc` | Junior-facing explainer voice — expand acronyms, intent over jargon *(globs only)* |
| `focus.mdc` | Diagnostic engine identity, HUD contract *(symlink → `cursor-rules/focus/`; **@-mention / requestable**)* |
| `focus-learning.mdc` | Learn-while-building technology map *(symlink; **@-mention / requestable**)* |
| `focus-mentorship.mdc` | Mentorship protocol *(symlink; **@-mention / requestable**)* |

Global rules (SWE standards, communication, owner profile) live in the private **`cursor-rules`** repo, symlinked to `~/.cursor/plugins/local/swe-standards`.

**Tip:** Open the Focus folder as the Cursor workspace (not parent `Cursor/`) so these project rules attach reliably. Pull demoted rules with `@focus`, `@focus-learning`, or `@focus-mentorship` when you need them.

Private hooks live in **`cursor-rules/focus/`** (local symlinks; gitignored here). See `cursor-rules` README.
