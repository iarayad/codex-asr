import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from codex_asr.engine import CodexASREngine, IBus


CHORD = IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK
RELEASE = IBus.ModifierType.RELEASE_MASK


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.engine = SimpleNamespace(
            shortcut_down=False, hold_started_at=None, busy=False,
            recorder=SimpleNamespace(has_recording=False),
        )

        def toggle():
            if not self.engine.busy:
                self.engine.recorder.has_recording = not self.engine.recorder.has_recording

        self.engine._toggle_recording = Mock(side_effect=toggle)
        self.clock = patch("codex_asr.engine.time.monotonic", return_value=10.0).start()
        self.addCleanup(patch.stopall)

    def key(self, state=CHORD, keyval=IBus.KEY_space):
        return CodexASREngine.do_process_key_event(self.engine, keyval, 0, state)

    def test_tap_then_tap_stops(self):
        self.assertTrue(self.key())
        self.assertTrue(self.engine.recorder.has_recording)
        self.clock.return_value = 10.1
        self.assertTrue(self.key(CHORD | RELEASE))
        self.assertTrue(self.engine.recorder.has_recording)
        self.key()
        self.key(CHORD | RELEASE)
        self.assertFalse(self.engine.recorder.has_recording)
        self.assertEqual(self.engine._toggle_recording.call_count, 2)

    def test_hold_stops_on_release_even_without_modifiers(self):
        self.key()
        self.clock.return_value = 11.0
        self.assertTrue(self.key(RELEASE))
        self.assertFalse(self.engine.recorder.has_recording)

    def test_autorepeat_does_not_toggle_or_reset_hold_time(self):
        self.key()
        self.clock.return_value = 11.0
        for _ in range(5):
            self.assertTrue(self.key())
        self.engine._toggle_recording.assert_called_once()
        self.key(RELEASE)
        self.assertFalse(self.engine.recorder.has_recording)

    def test_holding_stop_shortcut_does_not_restart(self):
        self.engine.recorder.has_recording = True
        self.key()
        self.clock.return_value = 11.0
        self.key()
        self.key(RELEASE)
        self.assertFalse(self.engine.recorder.has_recording)
        self.engine._toggle_recording.assert_called_once()

    def test_busy_press_does_not_start_after_transcription_finishes(self):
        self.engine.busy = True
        self.key()
        self.engine.busy = False
        self.clock.return_value = 11.0
        self.key()
        self.key(RELEASE)
        self.assertFalse(self.engine.recorder.has_recording)
        self.engine._toggle_recording.assert_called_once()

    def test_other_shortcuts_and_unmatched_releases_pass_through(self):
        for state in (0, IBus.ModifierType.CONTROL_MASK,
                      IBus.ModifierType.SHIFT_MASK, CHORD | IBus.ModifierType.MOD1_MASK,
                      CHORD | RELEASE):
            self.assertFalse(self.key(state))
        self.assertFalse(self.key(0, IBus.KEY_F8))
        self.engine._toggle_recording.assert_not_called()

    def test_caps_lock_does_not_block_shortcut(self):
        self.assertTrue(self.key(CHORD | IBus.ModifierType.LOCK_MASK))
        self.assertTrue(self.engine.recorder.has_recording)
