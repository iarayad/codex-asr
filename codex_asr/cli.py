from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
import time

from .config import load_config
from .transcribe import load_codex_auth, transcribe


def doctor() -> int:
    config = load_config()
    checks = {
        "system Python GObject bindings": _has_ibus_bindings(),
        "pw-record": shutil.which("pw-record") is not None,
        "notify-send": shutil.which("notify-send") is not None,
    }
    try:
        load_codex_auth(config.auth_file)
        checks["Codex ChatGPT auth token"] = True
    except RuntimeError:
        checks["Codex ChatGPT auth token"] = False

    for label, passed in checks.items():
        print(f"{'ok' if passed else 'MISSING':7} {label}")
    return 0 if all(checks.values()) else 1


def transcribe_file(path: str) -> int:
    try:
        print(transcribe(Path(path), load_config()))
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def diagnose() -> int:
    """Exercise the microphone and backend without relying on IBus notifications."""
    from .recorder import Recorder

    recorder = Recorder()
    stage = "configuration"
    try:
        config = load_config()
        load_codex_auth(config.auth_file)
        stage = "microphone recording"
        print(f"Recorder executable: {shutil.which('pw-record')}", flush=True)
        print("Speak now: recording for 5 seconds…", flush=True)
        recorder.start(verbose=True)
        time.sleep(5)
        path = recorder.stop()
        print(f"Recorded {path.stat().st_size} bytes. Contacting transcription backend…", flush=True)
        stage = "transcription"
        result = transcribe(path, config)
        print(f"Transcript: {result}" if result else "Backend responded, but detected no speech.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAILED during {stage}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled", file=sys.stderr)
        return 130
    finally:
        recorder.cancel()


def _has_ibus_bindings() -> bool:
    try:
        import gi

        gi.require_version("IBus", "1.0")
        from gi.repository import IBus  # noqa: F401

        return True
    except (ImportError, ValueError):
        return False


def run_engine() -> int:
    import gi

    gi.require_version("IBus", "1.0")
    from gi.repository import GLib, IBus

    from .engine import CodexASREngine

    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("error: cannot connect to IBus", file=sys.stderr)
        return 1

    factory = IBus.Factory.new(bus.get_connection())
    factory.add_engine("codex-asr", CodexASREngine)
    bus.request_name("org.freedesktop.IBus.CodexASR", 0)
    loop = GLib.MainLoop()
    bus.connect("disconnected", lambda *_args: loop.quit())
    loop.run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Codex-backed dictation for IBus")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="check runtime requirements")
    subparsers.add_parser("diagnose", help="record five seconds and test transcription")
    transcribe_parser = subparsers.add_parser(
        "transcribe", help="transcribe an audio file with the current Codex login"
    )
    transcribe_parser.add_argument("audio")
    subparsers.add_parser("engine", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return doctor()
    if args.command == "diagnose":
        return diagnose()
    if args.command == "transcribe":
        return transcribe_file(args.audio)
    return run_engine()


if __name__ == "__main__":
    raise SystemExit(main())
