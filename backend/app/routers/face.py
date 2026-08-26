from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.conversation import ChatSession, SessionProfile
from app.services.face_service import face_service


router = APIRouter(
    prefix="/api/face",
    tags=["Face"],
)


@router.post("/recognize")
async def recognize_face(
    image: UploadFile = File(...),

    # frontend ส่ง token เดิมกลับมาได้
    # เพื่อไม่ต้องสร้าง session ใหม่ทุก 2 วินาที
    session_token: str | None = Form(None),

    db: Session = Depends(get_db),
):
    """
    Face Recognition endpoint
    """

    image_bytes = await image.read()

    try:
        user, similarity = face_service.recognize(
            db,
            image_bytes,
        )

    except ValueError as error:
        error_code = str(error)

        if error_code == "NO_FACE":
            return {
                "status": "no_face",
                "recognized": False,
            }

        if error_code == "MULTIPLE_FACES":
            return {
                "status": "multiple_faces",
                "recognized": False,
            }

        raise

    # ------------------------------------------
    # ตรวจ session เดิม
    # ------------------------------------------

    chat_session = None

    if session_token:
        chat_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.token
                == session_token
            )
            .first()
        )

    # ------------------------------------------
    # Unknown user
    # ------------------------------------------

    if user is None:

        if chat_session is None:
            chat_session = ChatSession(
                user_id=None,
            )

            db.add(chat_session)

        chat_session.last_seen_at = datetime.utcnow()

        db.commit()
        db.refresh(chat_session)

        profile = db.get(
            SessionProfile,
            chat_session.id,
        )

        return {
            "status": "unknown",
            "recognized": False,
            "similarity": similarity,
            "session_token": chat_session.token,
            "claimed_name": (
                profile.claimed_name
                if profile is not None
                else None
            ),
        }

    # ------------------------------------------
    # Known user
    # ------------------------------------------

    # ถ้า session เดิมเป็นคนอื่น
    # สร้าง session ใหม่ทันที
    if (
        chat_session is None
        or chat_session.user_id != user.id
    ):
        chat_session = ChatSession(
            user_id=user.id,
        )

        db.add(chat_session)

    chat_session.last_seen_at = datetime.utcnow()

    db.commit()
    db.refresh(chat_session)

    return {
        "status": "recognized",
        "recognized": True,

        "user_id": user.id,
        "name": user.name,
        "role": user.role,

        "similarity": similarity,

        "session_token": chat_session.token,
    }
