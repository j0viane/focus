#!/usr/bin/env bash
# Launch Focus extension + repo in one isolated Cursor window.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$ROOT/extensions/vscode-focus"
CURSOR="${CURSOR_BIN:-/Applications/Cursor.app/Contents/Resources/app/bin/cursor}"
DEV_PROFILE="${TMPDIR:-/tmp}/cursor-focus-ext-dev"

if [[ ! -x "$CURSOR" ]]; then
  echo "Cursor CLI not found at: $CURSOR"
  echo "Install from Cursor: Cmd+Shift+P → Shell Command: Install 'cursor' command in PATH"
  exit 1
fi

echo "Compiling extension…"
(cd "$EXT" && npm run compile --silent)

echo ""
echo "IMPORTANT: Close ALL other Cursor windows first (especially the one with the red Stop square)."
echo "Press Enter when they're closed…"
read -r _

mkdir -p "$DEV_PROFILE"
WORKSPACE="$ROOT/Focus.code-workspace"

echo "Opening isolated dev window…"
exec "$CURSOR" \
  --user-data-dir="$DEV_PROFILE" \
  --new-window \
  --extensionDevelopmentPath="$EXT" \
  "$WORKSPACE"
