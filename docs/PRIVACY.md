# Focus — Privacy Model

Living document. Defines what data Focus reads, stores, transmits, and what never leaves the boundary.

**Last updated:** July 2026  
**Status:** Phase 0 — principles locked before application code

---

## Threat model (Phase 1 scope)

Focus operates on **source code the user already has access to** — local clones or GitHub repos where the Action is installed. Primary risks:

1. **Secret leakage** — API keys, tokens, or credentials in code sent to logs or LLM APIs
2. **Over-collection** — reading ignored files, binaries, or unrelated paths
3. **Third-party exposure** — graph or source sent to LLM providers beyond user intent
4. **Token over-permission** — GitHub PAT with broader scope than needed

---

## Data boundaries

### What Focus reads

| Source | Data | Notes |
|---|---|---|
| Local filesystem | Tracked source files under scan path | Respects `.gitignore` and `.focusignore` |
| Git | Diff hunks, file paths, commit SHAs | No full history mining beyond diff range |
| GitHub API | PR metadata, diff, file list | Action only; scoped token |

### What Focus does not read (by default)

- `.env`, `*.pem`, `*.key`, `secrets/` — excluded via gitignore patterns
- `node_modules/`, `.venv/`, build artifacts
- Binary files and lockfile contents (paths may appear; contents not parsed for HUD)
- Files outside the configured repository root

---

## LLM data policy (Phase 4c+)

When evidence-pack caption labeling is enabled (`FOCUS_LLM_ENABLED` / `--llm-captions` / `.focus.toml [llm] captions`):

| Sent to LLM | Never sent |
|---|---|
| `CaptionEvidencePack` JSON: symbol path/name, risk tier, implication who/what (already computed) | Full file contents / whole buffers |
| Capped changed edit lines only (~20 lines / ~1.5k chars) | `.env` values, API keys, JWT secrets |
| Measured slots (return/assign/callees/imports/blanks) + deterministic caption | Raw git patches with embedded secrets |
| Allowed token list (names the model may mention) | Entire repository tarball / full dependency graph |

**Still never invented by the model:** dependency edges, Mermaid nodes, hop counts, or risk tiers.

**Fail-closed label validation:** After the provider returns a caption, Focus keeps the deterministic ℹ️ unless the label clears pack grounding — no hop counts, no wrong risk word, no ``names`` / CamelCase / snake_case entities absent from the pack corpus, and no caller/downstream/depends claims unless implication (or other pack fields) already supports them. See `validate_label` in `src/focus/llm/validate.py`.

**Default:** off. Live-buffer overlay audits never call the labeler (latency + cost).

Provider requirements:

- **Ollama (local dogfood):** `FOCUS_LLM_PROVIDER=ollama` — pack stays on-machine; no paid key. Default model `qwen2.5:7b`.
- Cloud (`openai` / `anthropic`): use API endpoints with **no training** / enterprise privacy terms when analyzing private code
- Document provider choice in repo README when Action is configured
- Abort the call and keep the deterministic caption if secret-like patterns appear in edit lines

---

## Local processing

| Stage | Where it runs | Persisted? |
|---|---|---|
| Tree-sitter parse | Local / Action runner | Optional `.focus-cache/` (file-hash keyed AST index) |
| Dependency graph | In-memory / local cache | Cache is derived data; safe to delete |
| Blast radius | In-memory | Not persisted by default |
| HUD render | stdout or PR comment | PR comment is public to repo collaborators |

### Parse cache (`.focus-cache/`)

- Contains AST indices and graph edges — **derived from source**, not secrets if gitignore is correct
- Gitignored by default
- User can delete at any time (`focus scan --no-cache`)

---

## Secrets & credentials

| Rule | Implementation |
|---|---|
| Never commit `.env` | `.gitignore` + engineering rule |
| Never log secret values | Redact patterns: `API_KEY`, `TOKEN`, `PASSWORD`, `SECRET` |
| `.env.example` placeholders only | No real values in repo |
| GitHub Action uses `GITHUB_TOKEN` | Minimal permissions; no PAT in workflow logs |
| User LLM keys in env vars | `FOCUS_LLM_API_KEY` — loaded at runtime, never printed |

### Pre-flight secret scan (Phase 2+)

Before LLM calls, run a lightweight pattern scan on any string destined for external APIs. If high-entropy secret patterns match, **abort LLM call** and fall back to static labels.

---

## GitHub Action permissions

Minimum required (recommended):

```yaml
permissions:
  contents: read
  pull-requests: write
```

| Permission | Why |
|---|---|
| `contents: read` | Checkout repo for Tree-sitter index |
| `pull-requests: write` | Post/update Focus HUD comment |

Not required: `administration`, `issues: write`, `actions: write`, org-level secrets read.

---

## User control

| Control | Mechanism |
|---|---|
| Opt in | Install workflow explicitly |
| Opt out | Remove workflow file |
| Disable LLM | Config flag `llm_labels: false` |
| Ignore paths | `.focusignore` (same semantics as `.gitignore`) |
| Local-only mode | `focus audit --local` — nothing leaves machine |

---

## CI vs local

| Environment | Real repo code | LLM calls |
|---|---|---|
| Local dev | User's clone | User's API key; user responsibility |
| GitHub Action | Repo under analysis | Repo owner's configured key or none |
| Focus CI tests | **Synthetic fixture repos only** | Mocked / disabled |

Never run golden tests against private third-party repos without permission.

---

## Related documents

- [`ETHICS.md`](ETHICS.md) — responsible use, anti-surveillance
- [`TESTING.md`](TESTING.md) — synthetic fixtures, no real secrets in CI
- [`.cursor/rules/focus-engineering.mdc`](../.cursor/rules/focus-engineering.mdc) — credential isolation rule

Questions? [Open an issue](https://github.com/j0viane/focus/issues/new).
