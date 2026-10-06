import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from codex_asr.cli import diagnose


class DiagnoseTests(unittest.TestCase):
    def test_microphone_error_identifies_stage_and_cleans_up(self):
        recorder = MagicMock()
        recorder.start.side_effect = RuntimeError("microphone unavailable")
        output = io.StringIO()
        with patch("codex_asr.cli.load_codex_auth"), patch(
            "codex_asr.recorder.Recorder", return_value=recorder
        ), redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(diagnose(), 1)
        self.assertIn("FAILED during microphone recording: microphone unavailable", output.getvalue())
        recorder.cancel.assert_called_once()

    def test_backend_error_identifies_stage_and_cleans_up(self):
        recorder = MagicMock()
        recorder.stop.return_value = Path(__file__)
        output = io.StringIO()
        with patch("codex_asr.cli.load_codex_auth"), patch(
            "codex_asr.recorder.Recorder", return_value=recorder
        ), patch("codex_asr.cli.time.sleep"), patch(
            "codex_asr.cli.transcribe", side_effect=RuntimeError("HTTP 401")
        ), redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(diagnose(), 1)
        self.assertIn("FAILED during transcription: HTTP 401", output.getvalue())
        recorder.cancel.assert_called_once()
