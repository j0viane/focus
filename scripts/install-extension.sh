#!/usr/bin/env bash
# Install Focus extension into your normal Cursor (single window, no F5).
# Also refreshes the editable Python package so focus.path stays current.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$ROOT/extensions/vscode-focus"
VERSION="$(node -p "require('$EXT/package.json').version")"
VSIX="$EXT/focus-hud-${VERSION}.vsix"
CURSOR="${CURSOR_BIN:-/Applications/Cursor.app/Contents/Resources/app/bin/cursor}"

if [[ ! -x "$CURSOR" ]]; then
  echo "Cursor CLI not found at: $CURSOR"
  exit 1
fi

echo "Installing editable focus-hud (Python)…"
if command -v uv >/dev/null 2>&1; then
  (cd "$ROOT" && uv pip install -e .)
else
  (cd "$ROOT" && python3 -m pip install -e .)
fi

echo "Compiling and packaging Focus extension v${VERSION}…"
(cd "$EXT" && npm run compile --silent)
(cd "$EXT" && npx --yes @vscode/vsce package --allow-missing-repository --out "$VSIX" >/dev/null)

echo "Installing ${VSIX} into Cursor…"
"$CURSOR" --install-extension "$VSIX" --force

cat <<EOF

Installed Focus extension v${VERSION} + editable focus-hud. Next (in your Focus window):
  1. Cmd+Shift+P → "Developer: Reload Window"
  2. Open folder: $ROOT
  3. Cmd+Shift+P → "Focus: Audit Local Changes"
  4. Hover the status bar — tooltip should say "Focus extension v${VERSION}"

Reload alone does NOT pick up extension changes — re-run this script after pulls.

focus.path is already set in .vscode/settings.json for this repo.

Note: in zsh, trailing "# comments" on pasted commands are NOT ignored
(unless interactivecomments is set). Prefer this script alone — no comments needed.
EOF
