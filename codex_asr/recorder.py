from __future__ import annotations

import signal
import subprocess
import tempfile
import wave
from pathlib import Path


class Recorder:
    def __init__(self) -> None:
        self.path: Path | None = None
        self.process: subprocess.Popen[bytes] | None = None

    @property
    def is_recording(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def has_recording(self) -> bool:
        """Whether a capture was started, including one that failed asynchronously."""
        return self.process is not None

    def start(self, *, verbose: bool = False) -> Path:
        if self.process is not None:
            if self.is_recording:
                raise RuntimeError("Already recording")
            self.cancel()
        handle = tempfile.NamedTemporaryFile(prefix="codex-asr-", suffix=".wav", delete=False)
        handle.close()
        self.path = Path(handle.name)
        try:
            self.process = subprocess.Popen(
                [
                    "pw-record",
                    *(["--verbose"] if verbose else []),
                    "--rate",
                    "24000",
                    "--channels",
                    "1",
                    "--format",
                    "s16",
                    str(self.path),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                return_code = self.process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                return self.path

            stderr = self.process.stderr.read().decode("utf-8", errors="replace").strip()
            self.cancel()
            detail = f": {stderr}" if stderr else ""
            raise RuntimeError(f"pw-record exited with status {return_code}{detail}")
        except Exception:
            if self.path is not None:
                self.path.unlink(missing_ok=True)
                self.path = None
            self.process = None
            raise

    def stop(self) -> Path:
        if self.process is None or self.path is None:
            raise RuntimeError("Not recording")
        stopped_by_us = False
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                return_code = self.process.wait(timeout=5)
                stopped_by_us = True
            except subprocess.TimeoutExpired:
                self.process.kill()
                return_code = self.process.wait(timeout=2)
        else:
            return_code = self.process.returncode

        stderr = self.process.stderr.read().decode("utf-8", errors="replace").strip()
        self.process = None

        # PipeWire 1.6.2 exits 1 on SIGINT unless the stream was drained.
        # Accept this only for an intentional, graceful stop with valid audio.
        if return_code not in (0, -signal.SIGINT) and not (
            stopped_by_us and return_code == 1
        ):
            self.path.unlink(missing_ok=True)
            detail = f": {stderr}" if stderr else ""
            raise RuntimeError(f"pw-record exited with status {return_code}{detail}")
        try:
            with wave.open(str(self.path), "rb") as audio:
                if audio.getnframes() == 0:
                    raise RuntimeError("No microphone audio was recorded")
                frame_size = audio.getnchannels() * audio.getsampwidth()
                audio.setpos(audio.getnframes() - 1)
                if len(audio.readframes(1)) != frame_size:
                    raise RuntimeError("Microphone WAV recording is truncated")
        except (OSError, EOFError, wave.Error, RuntimeError) as exc:
            self.path.unlink(missing_ok=True)
            raise RuntimeError(f"Invalid microphone recording: {exc}") from exc
        return self.path

    def cancel(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=2)
        self.process = None
        if self.path:
            self.path.unlink(missing_ok=True)
            self.path = None
