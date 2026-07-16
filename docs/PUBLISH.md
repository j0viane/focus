# Publishing Focus to PyPI

Distribution name on PyPI: **`focus-hud`** (the name `focus` is already taken).  
CLI and import stay **`focus`**.

```bash
pip install focus-hud
focus version   # → 0.3.5
```

## One-time: Trusted Publishing

1. Create the project on [PyPI](https://pypi.org/manage/account/) (or let the first publish create it).
2. Add a Trusted Publisher for GitHub:
   - Owner: `j0viane`
   - Repository: `focus`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. In the GitHub repo, create an Environment named `pypi` (Settings → Environments).

## Release

```bash
git tag v0.3.5
git push origin v0.3.5
```

That runs [`.github/workflows/publish.yml`](../.github/workflows/publish.yml) (`uv build` + `pypa/gh-action-pypi-publish`).

Manual local publish (if you have an API token):

```bash
uv build
uv publish --token "$PYPI_TOKEN"
```

Install the published package: `pip install focus-hud`.
