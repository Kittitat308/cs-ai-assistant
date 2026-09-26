import asyncio

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.services.face_service import face_service
from app.services.ip_camera_service import IPCameraError, ip_camera_service
from app.services.conversation_session_service import (
    conversation_session_service,
)


router = APIRouter(
    prefix="/api/face",
    tags=["Face"],
)


@router.get("/camera/snapshot")
async def get_ip_camera_snapshot():
    """Proxy ภาพจาก IPv4 camera; frontend จะ fallback หาก endpoint ใช้ไม่ได้."""

    try:
        image, content_type = await asyncio.to_thread(
            ip_camera_service.fetch_snapshot,
            settings.ip_camera_url,
        )
    except IPCameraError as error:
        raise HTTPException(
            status_code=503,
            detail="IP camera unavailable",
        ) from error

    return Response(content=image, media_type=content_type)


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
            session = conversation_session_service.resolve_no_face_session(
                session_token
            )

            if session is not None and session.user_id is not None:
                verified_user = db.get(User, session.user_id)

                if verified_user is not None:
                    return {
                        "status": "recognized",
                        "recognized": True,
                        "user_id": verified_user.id,
                        "name": verified_user.name,
                        "role": verified_user.role,
                        "session_token": session.token,
                        "verify_user": session.verify_user,
                        "verify_fail_count": session.verify_fail_count,
                        "verification_pending": True,
                    }

            if session is not None:
                return {
                    "status": "unknown",
                    "recognized": False,
                    "session_token": session.token,
                    "verify_user": False,
                    "verify_fail_count": 0,
                    "verification_failed": True,
                }

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
            user_role=None,
            face_embedding=embedding.tolist(),
            face_threshold=settings.face_threshold,
        )

        if session.user_id is not None:
            verified_user = db.get(User, session.user_id)

            if verified_user is not None:
                return {
                    "status": "recognized",
                    "recognized": True,
                    "user_id": verified_user.id,
                    "name": verified_user.name,
                    "role": verified_user.role,
                    "similarity": similarity,
                    "session_token": session.token,
                    "verify_user": session.verify_user,
                    "verify_fail_count": session.verify_fail_count,
                    "verification_pending": True,
                }

        return {
            "status": "unknown",
            "recognized": False,
            "similarity": similarity,
            "session_token": session.token,
            "claimed_name": session.claimed_name,
            "verify_user": session.verify_user,
            "verify_fail_count": session.verify_fail_count,
            "verification_failed": session.verification_failed,
        }

    # ------------------------------------------
    # Known user
    # ------------------------------------------

    session = conversation_session_service.resolve_face_session(
        session_token,
        user_id=user.id,
        user_role=user.role,
        face_embedding=embedding.tolist(),
        face_threshold=settings.face_threshold,
    )

    if session.user_id != user.id:
        if session.user_id is not None:
            verified_user = db.get(User, session.user_id)

            if verified_user is not None:
                return {
                    "status": "recognized",
                    "recognized": True,
                    "user_id": verified_user.id,
                    "name": verified_user.name,
                    "role": verified_user.role,
                    "similarity": similarity,
                    "session_token": session.token,
                    "verify_user": session.verify_user,
                    "verify_fail_count": session.verify_fail_count,
                    "verification_pending": True,
                }

        return {
            "status": "unknown",
            "recognized": False,
            "similarity": similarity,
            "session_token": session.token,
            "verify_user": False,
            "verify_fail_count": 0,
            "verification_failed": session.verification_failed,
        }

    return {
        "status": "recognized",
        "recognized": True,

        "user_id": user.id,
        "name": user.name,
        "role": user.role,

        "similarity": similarity,

        "session_token": session.token,
        "verify_user": session.verify_user,
        "verify_fail_count": session.verify_fail_count,
        "verification_pending": session.verify_fail_count > 0,
    }
