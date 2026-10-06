from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_asr.config import load_config


class ConfigTests(unittest.TestCase):
    def test_defaults_need_no_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = load_config(Path(directory) / "missing.ini")
        self.assertEqual(config.endpoint, "https://chatgpt.com/backend-api/transcribe")
        self.assertIsNone(config.language)
        self.assertTrue(config.append_space)

    def test_config_and_environment_auth_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.ini"
            path.write_text("[codex]\nlanguage = es\nappend_space = false\n")
            auth_path = Path(directory) / "auth.json"
            with patch.dict(os.environ, {"CODEX_ASR_AUTH_FILE": str(auth_path)}):
                config = load_config(path)
        self.assertEqual(config.language, "es")
        self.assertFalse(config.append_space)
        self.assertEqual(config.auth_file, auth_path)


if __name__ == "__main__":
    unittest.main()
