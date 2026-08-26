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
from app.models.conversation import (
    ChatSession,
    Message,
    SessionProfile,
)
from app.services.ai_service import ai_service
from app.services.stt_service import stt_service
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
    Groq STT
      ↓
    Gemini
      ↓
    edge-tts
      ↓
    MP3
    """

    # -----------------------------------------
    # Validate session
    # -----------------------------------------

    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.token
            == session_token
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid session",
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

    user_text = await stt_service.transcribe(
        audio_bytes,
        filename=audio.filename or "audio.webm",
    )

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
    # Save conversation memory
    # -----------------------------------------

    db.add(
        Message(
            session_id=session.id,
            role="user",
            content=user_text,
        )
    )

    db.add(
        Message(
            session_id=session.id,
            role="assistant",
            content=assistant_text,
        )
    )

    db.commit()

    claimed_name = None

    if session.user_id is None:
        profile = db.get(SessionProfile, session.id)
        claimed_name = (
            profile.claimed_name
            if profile is not None
            else None
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
        "claimed_name": claimed_name,
    }
