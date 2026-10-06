#!/bin/sh
set -eu

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
LIB_HOME="$HOME/.local/lib/codex-asr"
BIN_HOME="$HOME/.local/bin"
COMPONENT_HOME="$DATA_HOME/ibus/component"

mkdir -p "$LIB_HOME" "$BIN_HOME" "$COMPONENT_HOME"
cp -R "$SOURCE_DIR/codex_asr" "$LIB_HOME/"
cp "$SOURCE_DIR/bin/codex-asr" "$BIN_HOME/codex-asr"
chmod 755 "$BIN_HOME/codex-asr"

sed "s|@EXEC@|$BIN_HOME/codex-asr|g" \
  "$SOURCE_DIR/packaging/codex-asr.xml.in" \
  > "$COMPONENT_HOME/codex-asr.xml"

printf '%s\n' \
  "Installed Codex ASR." \
  "" \
  "Next:" \
  "  1. Confirm ChatGPT auth: codex login status" \
  "  2. Run: $BIN_HOME/codex-asr doctor" \
  "  3. Log out and back in (or restart IBus)." \
  "  4. Add 'Codex Dictation' in Settings > Keyboard > Input Sources." \
  "  5. Select it, then use Ctrl+Shift+Space: tap to toggle or hold to talk."
