from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

from .config import Config, load_config
from .recorder import Recorder
from .transcribe import transcribe


def _notify(summary: str, body: str = "") -> None:
    try:
        subprocess.Popen(
            ["notify-send", "--app-name=Codex ASR", summary, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


class CodexASREngine(IBus.Engine):
    __gtype_name__ = "CodexASREngine"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.recorder = Recorder()
        self.busy = False
        self.config: Config | None = None
        self.focus_generation = 0
        self.shortcut_down = False
        self.hold_started_at: float | None = None

    def _show_status(self, text: str, visible: bool = True) -> None:
        self.update_auxiliary_text(IBus.Text.new_from_string(text), visible)

    def do_process_key_event(self, keyval: int, keycode: int, state: int) -> bool:
        del keycode
        if keyval != IBus.KEY_space:
            return False
        if state & IBus.ModifierType.RELEASE_MASK:
            if not self.shortcut_down:
                return False
            self.shortcut_down = False
            started_at = self.hold_started_at
            self.hold_started_at = None
            # A short tap leaves recording running; a hold ends on release.
            # Match the release even when Ctrl/Shift were released first.
            if (started_at is not None and time.monotonic() - started_at >= 0.4
                    and self.recorder.has_recording):
                self._toggle_recording()
            return True
        if self.shortcut_down:
            return True  # Ignore Space autorepeat while the shortcut is held.
        required = IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK
        extra = (IBus.ModifierType.MOD1_MASK | IBus.ModifierType.SUPER_MASK
                 | IBus.ModifierType.META_MASK | IBus.ModifierType.HYPER_MASK)
        if state & required != required or state & extra:
            return False
        self.shortcut_down = True
        self.hold_started_at = (
            time.monotonic() if not self.busy and not self.recorder.has_recording else None
        )
        self._toggle_recording()
        return True

    def _toggle_recording(self) -> None:
        if self.busy:
            _notify("Codex ASR", "Still transcribing the previous recording")
            return

        if not self.recorder.has_recording:
            try:
                self.config = load_config()
                self.recorder.start()
            except Exception as exc:
                self._fail(str(exc))
                return
            self._show_status("● Listening — Ctrl+Shift+Space to stop; release after holding to stop")
            _notify("Codex ASR", "Listening… tap Ctrl+Shift+Space again, or release after holding")
            return

        try:
            audio_path = self.recorder.stop()
        except Exception as exc:
            self._fail(str(exc))
            return

        self.busy = True
        self._show_status("Transcribing…")
        focus_generation = self.focus_generation
        thread = threading.Thread(
            target=self._transcribe_worker,
            args=(audio_path, self.config, focus_generation),
            daemon=True,
        )
        thread.start()

    def _transcribe_worker(
        self, audio_path: Path, config: Config | None, focus_generation: int
    ) -> None:
        try:
            if config is None:
                raise RuntimeError("Configuration disappeared")
            text = transcribe(audio_path, config)
            GLib.idle_add(self._finish, text, config.append_space, focus_generation)
        except Exception as exc:
            GLib.idle_add(self._fail, str(exc))
        finally:
            audio_path.unlink(missing_ok=True)

    def _finish(self, text: str, append_space: bool, focus_generation: int) -> bool:
        focus_unchanged = focus_generation == self.focus_generation
        if text and focus_unchanged:
            suffix = " " if append_space and not text.endswith((" ", "\n")) else ""
            self.commit_text(IBus.Text.new_from_string(text + suffix))
        self.busy = False
        self._show_status("", False)
        if not focus_unchanged:
            _notify("Codex ASR", "Transcript discarded because focus changed")
        else:
            _notify("Codex ASR", "Transcript inserted" if text else "No speech detected")
        return GLib.SOURCE_REMOVE

    def _fail(self, message: str) -> bool:
        self.busy = False
        self._show_status(f"ASR error: {message[:240]}", True)
        print(f"Codex ASR error: {message}", file=sys.stderr, flush=True)
        _notify("Codex ASR error", message)
        return GLib.SOURCE_REMOVE

    def do_focus_out(self) -> None:
        self.focus_generation += 1
        self.shortcut_down = False
        self.hold_started_at = None
        if self.recorder.has_recording:
            self.recorder.cancel()
            self._show_status("", False)
            _notify("Codex ASR", "Recording cancelled because focus changed")
        super().do_focus_out()
