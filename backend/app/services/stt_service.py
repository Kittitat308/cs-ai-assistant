import asyncio

from groq import APITimeoutError, Groq

from app.core.config import settings


class STTError(RuntimeError):
    """เกิดข้อผิดพลาดระหว่างเรียก Groq STT"""


class STTTimeoutError(STTError):
    """Groq STT ประมวลผลเกินเวลาที่กำหนด"""


class STTService:
    """Speech-to-Text ผ่าน Groq Whisper Large V3"""

    def __init__(self):
        self.client = Groq(
            api_key=settings.groq_api_key,
            timeout=settings.stt_timeout_seconds,
        )

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.webm",
        timeout_seconds: float | None = None,
    ) -> str:
        timeout = timeout_seconds or settings.stt_timeout_seconds

        def request_transcription() -> str:
            result = self.client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model=settings.groq_stt_model,
                language="th",
                response_format="json",
                temperature=0.0,
            )
            return result.text.strip()

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(request_transcription),
                timeout=timeout,
            )
        except (asyncio.TimeoutError, APITimeoutError, TimeoutError) as exc:
            raise STTTimeoutError("Groq STT request timed out") from exc
        except Exception as exc:
            raise STTError(f"Groq STT request failed: {exc}") from exc


stt_service = STTService()
