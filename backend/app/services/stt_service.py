import asyncio
import io
import json
import logging
import time
import uuid
import wave
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


logger = logging.getLogger(__name__)

# Whisper รับเสียง PCM สำหรับ warm-up ที่ 16 kHz ตามค่าที่ระบบกำหนด
SAMPLE_RATE = 16000


class STTError(RuntimeError):
    """เกิดข้อผิดพลาดระหว่างเรียก local whisper-server"""


class STTTimeoutError(STTError):
    """whisper-server ประมวลผลเกินเวลาที่กำหนด"""


class STTService:
    """Speech-to-Text ผ่าน Thonburian Whisper บน local whisper-server"""

    @staticmethod
    def _multipart_body(
        audio_bytes: bytes,
        filename: str,
    ) -> tuple[bytes, str]:
        boundary = f"----cs-ai-assistant-{uuid.uuid4().hex}"
        safe_filename = filename.replace('"', "")
        body = bytearray()
        body.extend(
            (
                f"--{boundary}\r\n"
                "Content-Disposition: form-data; name=\"file\"; "
                f"filename=\"{safe_filename}\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode("utf-8")
        )
        body.extend(audio_bytes)
        body.extend(
            (
                f"\r\n--{boundary}\r\n"
                "Content-Disposition: form-data; name=\"response_format\""
                "\r\n\r\njson\r\n"
                f"--{boundary}--\r\n"
            ).encode("utf-8")
        )
        return bytes(body), boundary

    @classmethod
    def _request_transcription(
        cls,
        audio_bytes: bytes,
        filename: str,
        timeout_seconds: float,
    ) -> str:
        body, boundary = cls._multipart_body(audio_bytes, filename)
        request = Request(
            settings.whisper_server_url,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise STTTimeoutError("Whisper request timed out") from exc
        except (HTTPError, URLError, OSError) as exc:
            raise STTError(f"Whisper request failed: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise STTError("Whisper returned invalid JSON") from exc

        text = payload.get("text")
        if not isinstance(text, str):
            raise STTError("Whisper response does not contain text")
        return text.strip()

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.webm",
        timeout_seconds: float | None = None,
    ) -> str:
        timeout = timeout_seconds or settings.stt_timeout_seconds

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._request_transcription,
                    audio_bytes,
                    filename,
                    timeout,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise STTTimeoutError("Whisper request timed out") from exc

    @staticmethod
    def _silent_wav(duration_seconds: float = 1.0) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(
                b"\x00\x00" * int(SAMPLE_RATE * duration_seconds)
            )
        return buffer.getvalue()

    async def warm_up(
        self,
        audio_bytes: bytes | None = None,
        filename: str = "warmup.wav",
    ) -> None:
        """รอ server พร้อมและส่งเสียงเงียบหนึ่งครั้งเพื่อโหลด model เข้าหน่วยความจำ"""

        if not settings.whisper_warmup_on_start:
            return

        deadline = time.monotonic() + settings.whisper_warmup_timeout_seconds
        last_error: Exception | None = None

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                await self.transcribe(
                    audio_bytes or self._silent_wav(),
                    filename=filename,
                    timeout_seconds=max(1.0, remaining),
                )
                logger.info("Thonburian Whisper warm-up completed")
                return
            except STTError as exc:
                last_error = exc
                await asyncio.sleep(min(2.0, max(0.0, remaining)))

        raise RuntimeError(
            "Thonburian Whisper warm-up did not complete in time"
        ) from last_error


stt_service = STTService()
