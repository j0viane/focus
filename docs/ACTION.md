# Focus GitHub Action — how to add the HUD to any repo
#
# Drop-in workflow: [examples/focus-action.yml](../examples/focus-action.yml)
# Privacy: [PRIVACY.md](PRIVACY.md)

## Add to your repository

1. Copy [`examples/focus-action.yml`](../examples/focus-action.yml) to `.github/workflows/focus.yml`.
2. Merge to your default branch.
3. Open a PR — Focus posts (and updates in place) a HUD comment.

Install from PyPI ([`PUBLISH.md`](PUBLISH.md)):

```bash
pip install focus-hud
```

CLI entry point remains `focus`.

## Permissions

| Permission | Why |
|---|---|
| `contents: read` | Checkout the PR |
| `pull-requests: write` | Post / update the HUD comment |

No other scopes. Focus does not send source to third-party model APIs.

## This monorepo

[`.github/workflows/focus.yml`](../.github/workflows/focus.yml) uses `uv sync --frozen` so PRs dogfood the checkout under test, not only the last PyPI release.
