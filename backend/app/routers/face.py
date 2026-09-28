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
    rotation: str = Form("none"),
    enhance: bool = Form(False),

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
            rotation=rotation,
            enhance=enhance,
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
            user_role=None,
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
        user_role=user.role,
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


@router.post("/detect")
async def detect_face(
    image: UploadFile = File(...),
    rotation: str = Form("none"),
    enhance: bool = Form(False),
):
    """ตรวจเฉพาะว่ามีใบหน้าหรือไม่ โดยไม่รัน ArcFace recognition."""

    image_bytes = await image.read()

    try:
        face_count = await asyncio.to_thread(
            face_service.detect_face_count,
            image_bytes,
            rotation,
            enhance,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "status": "detected" if face_count > 0 else "no_face",
        "face_detected": face_count > 0,
        "face_count": face_count,
    }


@router.post("/session/end")
async def end_face_session(session_token: str = Form(...)):
    conversation_session_service.delete_session(session_token)
    return {"status": "ended"}
