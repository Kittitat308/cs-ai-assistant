from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.face_service import face_service
from app.services.conversation_session_service import (
    conversation_session_service,
)


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
        user, similarity, embedding = face_service.recognize_with_embedding(
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

    if user is None:
        session = conversation_session_service.resolve_face_session(
            session_token,
            user_id=None,
            face_embedding=embedding.tolist(),
            face_threshold=settings.face_threshold,
        )

        return {
            "status": "unknown",
            "recognized": False,
            "similarity": similarity,
            "session_token": session.token,
            "claimed_name": session.claimed_name,
        }

    # ------------------------------------------
    # Known user
    # ------------------------------------------

    session = conversation_session_service.resolve_face_session(
        session_token,
        user_id=user.id,
        face_embedding=embedding.tolist(),
        face_threshold=settings.face_threshold,
    )

    return {
        "status": "recognized",
        "recognized": True,

        "user_id": user.id,
        "name": user.name,
        "role": user.role,

        "similarity": similarity,

        "session_token": session.token,
    }
