import asyncio
import io
import os
import time
import unittest
import wave


os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("ADMIN_TOKEN", "test")


from app.services.stt_service import (  # noqa: E402
    SAMPLE_RATE,
    STTService,
    STTTimeoutError,
)


class SlowSTTService(STTService):
    @classmethod
    def _request_transcription(cls, audio_bytes, filename, timeout_seconds):
        time.sleep(0.2)
        return "ไม่ควรได้รับข้อความนี้"


class STTServiceTests(unittest.TestCase):
    def test_warmup_wav_is_16khz_mono_pcm(self):
        audio = STTService._silent_wav()

        with wave.open(io.BytesIO(audio), "rb") as wav_file:
            self.assertEqual(wav_file.getframerate(), SAMPLE_RATE)
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.getsampwidth(), 2)
            self.assertEqual(wav_file.getnframes(), SAMPLE_RATE)

    def test_transcription_has_hard_timeout(self):
        with self.assertRaises(STTTimeoutError):
            asyncio.run(
                SlowSTTService().transcribe(
                    b"audio",
                    timeout_seconds=0.01,
                )
            )

    def test_multipart_contains_audio_and_response_format(self):
        body, boundary = STTService._multipart_body(
            b"sample-audio",
            'recording".webm',
        )

        self.assertIn(b"sample-audio", body)
        self.assertIn(b'name="response_format"', body)
        self.assertIn(b"json", body)
        self.assertNotIn(b'recording".webm', body)
        self.assertTrue(boundary.startswith("----cs-ai-assistant-"))


if __name__ == "__main__":
    unittest.main()
