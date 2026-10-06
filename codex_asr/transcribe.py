from __future__ import annotations

import base64
import json
import os
import platform
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Config

DEFAULT_ENDPOINT = "https://chatgpt.com/backend-api/transcribe"
DEFAULT_DESKTOP_VERSION = "26.429.30905"


@dataclass(frozen=True)
class CodexAuth:
    access_token: str
    account_id: str | None
    path: Path


def default_auth_file() -> Path:
    explicit = os.environ.get("CODEX_ASR_AUTH_FILE")
    if explicit:
        return Path(explicit).expanduser()
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "auth.json"
    return Path.home() / ".codex" / "auth.json"


def load_codex_auth(path: Path | None = None) -> CodexAuth:
    path = path or default_auth_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Could not read Codex auth at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse Codex auth at {path}: {exc}") from exc

    mode = payload.get("auth_mode", payload.get("authMode"))
    if mode not in (None, "chatgpt", "chatgpt_auth_tokens"):
        raise RuntimeError(
            f"Codex auth mode is {mode!r}, not ChatGPT login. Run 'codex login'."
        )
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise RuntimeError(f"Codex auth at {path} has no ChatGPT tokens")
    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise RuntimeError(f"Codex auth at {path} has no ChatGPT access token")
    account_id = tokens.get("account_id")
    if not isinstance(account_id, str) or not account_id:
        account_id = _account_id_from_jwt(access_token)
    return CodexAuth(access_token.strip(), account_id, path)


def _account_id_from_jwt(token: str) -> str | None:
    try:
        encoded = token.split(".")[1]
        encoded += "=" * (-len(encoded) % 4)
        claims = json.loads(base64.urlsafe_b64decode(encoded))
    except (IndexError, ValueError, json.JSONDecodeError):
        return None

    for key in ("https://api.openai.com/auth", "https://openai.com/auth"):
        nested = claims.get(key)
        if isinstance(nested, dict):
            account_id = nested.get("chatgpt_account_id") or nested.get("account_id")
            if isinstance(account_id, str) and account_id:
                return account_id
    for key in ("chatgpt_account_id", "account_id"):
        account_id = claims.get(key)
        if isinstance(account_id, str) and account_id:
            return account_id
    return None


def _multipart(audio_path: Path, language: str | None = None) -> tuple[bytes, str]:
    boundary = f"codex-asr-{uuid.uuid4().hex}"
    mime = _content_type(audio_path)
    chunks: list[bytes] = []
    if language:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="language"\r\n\r\n',
                language.encode("utf-8"),
                b"\r\n",
            ]
        )
    safe_name = audio_path.name.replace('"', "")
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{safe_name}"\r\n'
            ).encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            audio_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


def _content_type(audio_path: Path) -> str:
    return {
        ".wav": "audio/wav",
        ".wave": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".oga": "audio/ogg",
        ".webm": "audio/webm",
    }.get(audio_path.suffix.lower(), "application/octet-stream")


def transcribe(audio_path: Path, config: Config, timeout: float = 300) -> str:
    auth = load_codex_auth(config.auth_file)
    body, boundary = _multipart(audio_path, config.language)
    headers = {
        "Authorization": f"Bearer {auth.access_token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Originator": "Codex Desktop",
        "User-Agent": (
            f"Codex Desktop/{DEFAULT_DESKTOP_VERSION} "
            f"({platform.system().lower()}; {platform.machine()})"
        ),
    }
    if auth.account_id:
        headers["ChatGPT-Account-Id"] = auth.account_id

    request = Request(config.endpoint, data=body, method="POST", headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-2000:]
        if exc.code == 401:
            detail = "ChatGPT login was rejected; run 'codex login' to refresh it"
        raise RuntimeError(f"Codex transcription returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Codex transcription: {exc.reason}") from exc

    text = payload.get("text")
    if not isinstance(text, str):
        raise RuntimeError("Codex transcription response did not contain text")
    return text.strip()
