import edge_tts

from app.core.config import settings


class TTSService:
    """
    Text-to-Speech ผ่าน edge-tts

    ไม่ต้องใช้ API key
    """

    async def synthesize(
        self,
        text: str,
    ) -> bytes:
        """
        แปลงข้อความเป็น MP3

        รับข้อมูล audio stream โดยตรง
        โดยไม่ต้องสร้างไฟล์ชั่วคราวบน server
        """

        communicate = edge_tts.Communicate(
            text=text,
            voice=settings.tts_voice,
            rate=settings.tts_rate,
            volume=settings.tts_volume,
            pitch=settings.tts_pitch,
        )

        audio_data = bytearray()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(
                    chunk["data"]
                )

        return bytes(audio_data)


tts_service = TTSService()