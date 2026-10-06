import io
import signal
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock

from codex_asr.recorder import Recorder


class RecorderStopTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.recorder = Recorder()
        self.recorder.path = Path(self.directory.name) / "recording.wav"
        self.process = MagicMock()
        self.process.poll.return_value = None
        self.process.wait.return_value = 1
        self.process.stderr = io.BytesIO(b"recording.wav\n")
        self.recorder.process = self.process

    def write_audio(self, frames=2400):
        with wave.open(str(self.recorder.path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(b"\x01\x00" * frames)

    def test_intentional_stop_accepts_exit_one_with_valid_audio(self):
        self.write_audio()
        self.assertEqual(self.recorder.stop(), self.recorder.path)
        self.process.send_signal.assert_called_once_with(signal.SIGINT)
        self.assertTrue(self.recorder.path.exists())

    def test_unexpected_exit_one_remains_an_error(self):
        self.write_audio()
        self.process.poll.return_value = 1
        self.process.returncode = 1
        with self.assertRaisesRegex(RuntimeError, "exited with status 1"):
            self.recorder.stop()
        self.assertFalse(self.recorder.path.exists())

    def test_empty_wav_remains_an_error(self):
        self.write_audio(frames=0)
        with self.assertRaisesRegex(RuntimeError, "No microphone audio"):
            self.recorder.stop()
        self.assertFalse(self.recorder.path.exists())

    def test_invalid_file_remains_an_error(self):
        self.recorder.path.write_bytes(b"not a WAV" * 20)
        with self.assertRaisesRegex(RuntimeError, "Invalid microphone recording"):
            self.recorder.stop()
        self.assertFalse(self.recorder.path.exists())

    def test_truncated_file_remains_an_error(self):
        self.write_audio()
        data = self.recorder.path.read_bytes()
        self.recorder.path.write_bytes(data[:-10])
        with self.assertRaisesRegex(RuntimeError, "truncated"):
            self.recorder.stop()

    def test_forced_stop_remains_an_error(self):
        self.write_audio()
        self.process.wait.side_effect = [subprocess.TimeoutExpired("pw-record", 5), 1]
        with self.assertRaisesRegex(RuntimeError, "exited with status 1"):
            self.recorder.stop()
        self.process.kill.assert_called_once()
