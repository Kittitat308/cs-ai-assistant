from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    รวม configuration ของ backend ทั้งหมด

    ค่าจริงจะอ่านจากไฟล์ backend/.env
    จึงไม่จำเป็นต้องเขียน API key ไว้ใน source code
    """

    # Application
    app_name: str = "CS AI Assistant"
    debug: bool = True

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # PostgreSQL
    database_url: str

    # Groq STT
    groq_api_key: str
    groq_stt_model: str = "whisper-large-v3"
    stt_timeout_seconds: float = 6.0

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-3.1-flash-lite-preview"
    gemini_timeout_seconds: float = 10.0

    # Edge TTS
    tts_voice: str = "th-TH-NiwatNeural"
    tts_rate: str = "+0%"
    tts_volume: str = "+0%"
    tts_pitch: str = "+0Hz"

    # Face Recognition
    face_model: str = "buffalo_m"
    face_detection_size: int = 640
    face_threshold: float = 0.45
    ip_camera_url: str = "http://192.168.0.11:8080"

    # Admin API
    admin_token: str

    # บอก Pydantic ให้อ่านค่าจาก .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """
    สร้าง Settings เพียงครั้งเดียว
    แล้ว reuse ตลอดอายุของ application
    """

    return Settings()


settings = get_settings()
