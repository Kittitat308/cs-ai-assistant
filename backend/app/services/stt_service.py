import asyncio

from groq import Groq

from app.core.config import settings


class STTService:
    """
    Speech-to-Text ผ่าน Groq Whisper Large V3 Turbo
    """

    def __init__(self):
        # API key มาจาก backend/.env เท่านั้น
        self.client = Groq(
            api_key=settings.groq_api_key,
        )

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.webm",
    ) -> str:
        """
        ส่งไฟล์เสียงไป Groq

        ใช้ asyncio.to_thread เพราะ Groq SDK call นี้
        เป็น synchronous call
        """

        def _transcribe():
            result = self.client.audio.transcriptions.create(
                file=(
                    filename,
                    audio_bytes,
                ),
                model=settings.groq_stt_model,

                language="th",
                # json ทำให้เราต้องการเพียง transcription
                response_format="json",

                # ไม่ระบุ language เพื่อรองรับ
                # ภาษาไทย + อังกฤษในประโยคเดียวกัน
                temperature=0.0,
            )

            return result.text.strip()

        return await asyncio.to_thread(
            _transcribe
        )


stt_service = STTService()