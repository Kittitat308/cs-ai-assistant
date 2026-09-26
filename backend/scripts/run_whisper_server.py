"""Run whisper.cpp server with the tuned Thonburian Whisper settings."""

import subprocess
import sys
from pathlib import Path

# Whisper uses 16 kHz audio. The FastAPI warm-up uses the same sample rate.
SAMPLE_RATE = 16000
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402


def resolve_from_backend(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()


def main() -> int:
    executable = resolve_from_backend(settings.whisper_server_exe)
    model = resolve_from_backend(settings.whisper_model_path)

    if not executable.is_file():
        raise FileNotFoundError(f"whisper-server not found: {executable}")
    if not model.is_file():
        raise FileNotFoundError(f"Whisper model not found: {model}")

    command = [
        str(executable),
        # Thonburian Whisper model
        "-m",
        str(model),
        # Server IP
        "--host",
        settings.whisper_server_host,
        # Server Port
        "--port",
        str(settings.whisper_server_port),
        # Disable temperature fallback and suppress non-speech tokens
        "-nf",
        "-sns",
        # Use one decoding candidate
        "-bo",
        "1",
        # Do not use previous text as context
        "-mc",
        "0",
        # Thai language and Raspberry Pi CPU threads
        "-l",
        "th",
        "-t",
        str(settings.whisper_threads),
        # Browser sends WebM/Opus; whisper-server uses ffmpeg to convert it
        "--convert",
    ]

    return subprocess.call(command, cwd=BACKEND_DIR)


if __name__ == "__main__":
    sys.exit(main())
