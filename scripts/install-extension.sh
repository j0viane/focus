#!/usr/bin/env bash
# Install Focus extension into your normal Cursor (single window, no F5).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$ROOT/extensions/vscode-focus"
VSIX="$EXT/focus-hud-0.2.0.vsix"
CURSOR="${CURSOR_BIN:-/Applications/Cursor.app/Contents/Resources/app/bin/cursor}"

if [[ ! -x "$CURSOR" ]]; then
  echo "Cursor CLI not found at: $CURSOR"
  exit 1
fi

echo "Compiling and packaging extension…"
(cd "$EXT" && npm run compile --silent)
(cd "$EXT" && npx --yes @vscode/vsce package --allow-missing-repository --out "$VSIX" >/dev/null)

echo "Installing Focus extension into Cursor…"
"$CURSOR" --install-extension "$VSIX" --force

cat <<EOF

Installed. Next (in any normal Cursor window):
  1. Cmd+Shift+P → "Developer: Reload Window"
  2. Open folder: $ROOT
  3. Cmd+Shift+P → "Focus: Audit Local Changes"

focus.path is already set in .vscode/settings.json for this repo.
EOF
