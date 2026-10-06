from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    language: str | None = None
    append_space: bool = True
    endpoint: str = "https://chatgpt.com/backend-api/transcribe"
    auth_file: Path | None = None


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "codex-asr" / "config.ini"


def load_config(path: Path | None = None) -> Config:
    parser = configparser.ConfigParser()
    path = path or config_path()
    if path.exists():
        parser.read(path)

    section = parser["codex"] if parser.has_section("codex") else {}
    auth_file_value = os.environ.get("CODEX_ASR_AUTH_FILE") or section.get(
        "auth_file", ""
    )
    language = section.get("language", "").strip() or None
    append_space = str(section.get("append_space", "true")).lower() in {
        "1",
        "yes",
        "true",
        "on",
    }
    return Config(
        language=language,
        append_space=append_space,
        endpoint=section.get(
            "endpoint", "https://chatgpt.com/backend-api/transcribe"
        ).strip(),
        auth_file=Path(auth_file_value).expanduser() if auth_file_value else None,
    )
