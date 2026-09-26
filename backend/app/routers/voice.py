import base64

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.ai_service import ai_service
from app.services.conversation_session_service import (
    conversation_session_service,
)
from app.services.stt_service import STTTimeoutError, stt_service
from app.services.tts_service import tts_service


router = APIRouter(
    prefix="/api/voice",
    tags=["Voice"],
)


@router.post("/converse")
async def converse(
    session_token: str = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Pipeline หลักของ Voice Assistant

    Audio
      ↓
    Local Thonburian Whisper STT
      ↓
    Gemini
      ↓
    edge-tts
      ↓
    MP3
    """

    # -----------------------------------------
    # Resolve session ใน memory; ถ้า token หายหลัง reset/restart
    # ให้สร้าง Guest session ใหม่และทำ pipeline ต่อทันที
    # -----------------------------------------

    session = conversation_session_service.get_or_create_for_voice(
        session_token
    )

    # -----------------------------------------
    # Read audio
    # -----------------------------------------

    audio_bytes = await audio.read()

    if not audio_bytes:
        raise HTTPException(
            status_code=400,
            detail="Empty audio",
        )

    # -----------------------------------------
    # Speech-to-Text
    # -----------------------------------------

    try:
        user_text = await stt_service.transcribe(
            audio_bytes,
            filename=audio.filename or "audio.webm",
        )
    except STTTimeoutError:
        assistant_text = "ขอโทษครับ คุณพูดว่าอะไรนะ"
        mp3_bytes = await tts_service.synthesize(assistant_text)
        return {
            "user_text": "",
            "assistant_text": assistant_text,
            "audio": base64.b64encode(mp3_bytes).decode("ascii"),
            "audio_mime_type": "audio/mpeg",
            "claimed_name": session.claimed_name,
            "session_token": session.token,
        }

    if not user_text:
        raise HTTPException(
            status_code=400,
            detail="ไม่พบเสียงพูด",
        )

    # -----------------------------------------
    # Gemini
    # -----------------------------------------

    assistant_text = await ai_service.generate_reply(
        db,
        session,
        user_text,
    )

    # -----------------------------------------
    # Save conversation memory ใน Python เท่านั้น
    # -----------------------------------------

    conversation_session_service.append_exchange(
        session,
        user_text,
        assistant_text,
    )

    # -----------------------------------------
    # Text-to-Speech
    # -----------------------------------------

    mp3_bytes = await tts_service.synthesize(
        assistant_text
    )

    # MVP ใช้ Base64 เพื่อส่งข้อความและเสียง
    # ใน JSON response เดียวกัน
    audio_base64 = base64.b64encode(
        mp3_bytes
    ).decode("ascii")

    return {
        "user_text": user_text,
        "assistant_text": assistant_text,

        "audio": audio_base64,
        "audio_mime_type": "audio/mpeg",
        "claimed_name": session.claimed_name,
        "session_token": session.token,
    }
