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

    # SQLite database path (relative paths are resolved from backend/)
    database_path: str = "data/cs_ai_assistant.db"
    # รองรับ DATABASE_URL เดิมเฉพาะช่วง migration; ตัวแอปจะไม่ใช้ค่านี้เชื่อมต่อ
    database_url: str | None = None

    # Legacy Groq values are accepted during migration but are no longer used.
    groq_api_key: str | None = None
    groq_stt_model: str | None = None

    # Local Thonburian Whisper server
    whisper_server_url: str = "http://127.0.0.1:8178/inference"
    whisper_server_exe: str = "whisper.cpp/build/bin/whisper-server"
    whisper_model_path: str = "models/distill-thonburian-medium-q5_0.bin"
    whisper_server_host: str = "127.0.0.1"
    whisper_server_port: int = 8178
    whisper_threads: int = 4
    whisper_warmup_on_start: bool = True
    whisper_warmup_timeout_seconds: float = 180.0
    stt_timeout_seconds: float = 6.0

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_seconds: float = 6.0

    # Edge TTS
    tts_voice: str = "th-TH-NiwatNeural"
    tts_rate: str = "+0%"
    tts_volume: str = "+0%"
    tts_pitch: str = "+0Hz"

    # Face Recognition
    face_model: str = "buffalo_l"
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
