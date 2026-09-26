"""Warm up local Whisper with a short Thai speech sample before FastAPI starts."""

import asyncio
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.stt_service import stt_service  # noqa: E402
from app.services.tts_service import tts_service  # noqa: E402


async def main() -> None:
    warmup_audio = await tts_service.synthesize("ทดสอบระบบ")
    await stt_service.warm_up(
        warmup_audio,
        filename="warmup.mp3",
    )
    print("Thonburian Whisper warm-up completed")


if __name__ == "__main__":
    asyncio.run(main())
