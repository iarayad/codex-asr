#!/bin/sh
set -eu

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$SOURCE_DIR/install.sh"
"$HOME/.local/bin/codex-asr" doctor

# Ubuntu's IBus registry scans the system component directory, not XDG_DATA_HOME.
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
sudo install -m 644 "$DATA_HOME/ibus/component/codex-asr.xml" \
    /usr/share/ibus/component/codex-asr.xml
ibus write-cache

/usr/bin/python3 - <<'PY'
from gi.repository import Gio, GLib

settings = Gio.Settings.new("org.gnome.desktop.input-sources")
sources = list(settings.get_value("sources").unpack())
source = ("ibus", "codex-asr")
if source not in sources:
    sources.append(source)
    if not settings.set_value("sources", GLib.Variant("a(ss)", sources)):
        raise SystemExit("Could not save GNOME input sources")
    Gio.Settings.sync()
print("Codex Dictation added; existing input sources preserved.")
PY

printf '%s\n' "Log out and back in, select Codex Dictation, and use Ctrl+Shift+Space: tap to toggle or hold to talk."
