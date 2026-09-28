import asyncio
import os
import time
import unittest
from types import SimpleNamespace


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost/test",
)
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("ADMIN_TOKEN", "test")


from app.services.stt_service import (  # noqa: E402
    STTError,
    STTService,
    STTTimeoutError,
)


class FakeTranscriptions:
    def __init__(self, result=" ข้อความทดสอบ ", delay=0.0, error=None):
        self.result = result
        self.delay = delay
        self.error = error
        self.arguments = None

    def create(self, **kwargs):
        self.arguments = kwargs
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.result)


class STTServiceTests(unittest.TestCase):
    @staticmethod
    def service_with(transcriptions):
        service = object.__new__(STTService)
        service.client = SimpleNamespace(
            audio=SimpleNamespace(transcriptions=transcriptions)
        )
        return service

    def test_transcription_uses_large_v3_and_thai(self):
        transcriptions = FakeTranscriptions()
        service = self.service_with(transcriptions)

        text = asyncio.run(service.transcribe(b"audio", "speech.webm"))

        self.assertEqual(text, "ข้อความทดสอบ")
        self.assertEqual(
            transcriptions.arguments["model"],
            "whisper-large-v3",
        )
        self.assertEqual(transcriptions.arguments["language"], "th")
        self.assertEqual(transcriptions.arguments["response_format"], "json")

    def test_transcription_has_hard_timeout(self):
        service = self.service_with(FakeTranscriptions(delay=0.2))

        with self.assertRaises(STTTimeoutError):
            asyncio.run(
                service.transcribe(
                    b"audio",
                    timeout_seconds=0.01,
                )
            )

    def test_provider_error_is_wrapped(self):
        service = self.service_with(
            FakeTranscriptions(error=RuntimeError("provider failed"))
        )

        with self.assertRaises(STTError):
            asyncio.run(service.transcribe(b"audio"))


if __name__ == "__main__":
    unittest.main()
