# Focus demo (portfolio walkthrough)

Evidence-only blast radius — no LLM. These HUDs were generated from this repo with the shipped CLI.

## 1. Golden fixture (Python) — shared auth hub

```bash
uv run focus trace tests/fixtures/glass_box/auth_utils.py \
  --root tests/fixtures/glass_box \
  --out docs/examples/focus-hud-glass-box.md
```

**What you should see:** **CRITICAL** — 4 downstream files, up to 2 hops. Danger Zone: `api/routes.py`. Billing, dashboard, and jobs import `auth_utils` directly.

Full HUD: [`examples/focus-hud-glass-box.md`](examples/focus-hud-glass-box.md) (open in Markdown preview for Mermaid).

## 2. Same shape in TypeScript

```bash
uv run focus trace tests/fixtures/glass_box_js/authUtils.ts \
  --root tests/fixtures/glass_box_js \
  --out docs/examples/focus-hud-glass-box-js.md
```

**What you should see:** Same blast-radius story on ESM relative imports — Danger Zone `api/routes.ts`.

Full HUD: [`examples/focus-hud-glass-box-js.md`](examples/focus-hud-glass-box-js.md).

## 3. Dogfood — Focus on Focus

```bash
uv run focus trace src/focus/hud/classify.py --root . \
  --out docs/examples/focus-hud-classify.md
```

**What you should see:** Changing the Danger Zone classifier fans out through audit/CLI/config — **CRITICAL**, multi-hop, named importers (not threshold jargon).

Full HUD: [`examples/focus-hud-classify.md`](examples/focus-hud-classify.md).

## 4. PR comment (live)

This repo’s Action posts (and **updates in place**) a Focus HUD on pull requests. Example PRs: [#2](https://github.com/j0viane/focus/pull/2), [#4](https://github.com/j0viane/focus/pull/4), [#5](https://github.com/j0viane/focus/pull/5).

**Interview one-liner:** Focus answers “what else could break?” with a computed import graph — CLI locally, same HUD on the PR, no model inventing edges.
