from __future__ import annotations

import base64
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from codex_asr.config import Config
from codex_asr.transcribe import (
    _account_id_from_jwt,
    _multipart,
    load_codex_auth,
    transcribe,
)


def _jwt(claims: dict[str, object]) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


class AuthTests(unittest.TestCase):
    def test_loads_chatgpt_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            path.write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "tokens": {
                            "access_token": "secret-token",
                            "account_id": "acct_test",
                        },
                    }
                )
            )
            auth = load_codex_auth(path)
        self.assertEqual(auth.access_token, "secret-token")
        self.assertEqual(auth.account_id, "acct_test")

    def test_rejects_api_key_auth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            path.write_text(json.dumps({"auth_mode": "apikey"}))
            with self.assertRaisesRegex(RuntimeError, "not ChatGPT login"):
                load_codex_auth(path)

    def test_decodes_account_id_from_jwt(self) -> None:
        token = _jwt(
            {"https://api.openai.com/auth": {"chatgpt_account_id": "acct_nested"}}
        )
        self.assertEqual(_account_id_from_jwt(token), "acct_nested")


class MultipartTests(unittest.TestCase):
    def test_request_contains_audio_and_language_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "speech.wav"
            audio.write_bytes(b"RIFF-audio")
            body, boundary = _multipart(audio, "en")
        self.assertIn(f"--{boundary}".encode(), body)
        self.assertIn(b'name="language"', body)
        self.assertIn(b'name="file"; filename="speech.wav"', body)
        self.assertIn(b"RIFF-audio", body)
        self.assertNotIn(b"model", body)

    def test_transcribe_uses_codex_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            auth_path = root / "auth.json"
            auth_path.write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "tokens": {
                            "access_token": "secret-token",
                            "account_id": "acct_test",
                        },
                    }
                )
            )
            audio = root / "speech.wav"
            audio.write_bytes(b"RIFF-audio")
            response = BytesIO(b'{"text":"hello"}')
            response.__enter__ = lambda: response
            response.__exit__ = lambda *_args: None
            with patch("codex_asr.transcribe.urlopen", return_value=response) as call:
                text = transcribe(audio, Config(auth_file=auth_path))

        request = call.call_args.args[0]
        self.assertEqual(text, "hello")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(request.get_header("Chatgpt-account-id"), "acct_test")
        self.assertEqual(request.get_header("Originator"), "Codex Desktop")


if __name__ == "__main__":
    unittest.main()
