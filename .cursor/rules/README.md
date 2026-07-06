# Focus Cursor Rules

Project-specific rules loaded by Cursor when you work in this repo.

| File | Purpose |
|---|---|
| `focus-project.mdc` | Product context, architecture, tech stack *(public, committed)* |
| `focus-engineering.mdc` | Non-negotiable engineering constraints *(public, committed)* |
| `focus.mdc` | Diagnostic engine identity, HUD contract, directives *(symlink → `cursor-rules/focus/`)* |
| `focus-learning.mdc` | Learn-while-building technology map *(symlink → `cursor-rules/focus/`)* |
| `focus-mentorship.mdc` | Mentorship protocol *(symlink → `cursor-rules/focus/`)* |

Global rules (SWE standards, communication, owner profile) live in the private **`cursor-rules`** repo, symlinked to `~/.cursor/plugins/local/swe-standards`.
