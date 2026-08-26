from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.face import FaceEmbedding
from app.models.user import User
from app.schemas.api import CreateUserRequest
from app.services.face_service import face_service


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
)


def verify_admin(
    x_admin_token: str = Header(...),
):
    """
    Admin endpoint ทุกตัวต้องส่ง

    X-Admin-Token

    token จริงอยู่ใน backend/.env
    """

    if x_admin_token != settings.admin_token:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin token",
        )


@router.post(
    "/users",
    dependencies=[Depends(verify_admin)],
)
def create_user(
    data: CreateUserRequest,
    db: Session = Depends(get_db),
):
    """
    สร้างนักศึกษา / อาจารย์

    ผู้ใช้ทั่วไปไม่มี endpoint
    สำหรับเปลี่ยนตัวเองเป็น student/lecturer
    """

    existing = (
        db.query(User)
        .filter(
            User.external_id
            == data.external_id
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="รหัสนี้มีอยู่แล้ว",
        )

    user = User(
        external_id=data.external_id,
        name=data.name,
        role=data.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "external_id": user.external_id,
        "name": user.name,
        "role": user.role,
    }


@router.post(
    "/faces/enroll",
    dependencies=[Depends(verify_admin)],
)
async def enroll_face(
    user_id: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    ลงทะเบียนใบหน้า

    สามารถเรียก endpoint เดิมหลายครั้ง
    เพื่อเก็บหลายมุมหน้าของผู้ใช้หนึ่งคน
    """

    user = db.get(
        User,
        user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    image_bytes = await image.read()

    try:
        embedding = (
            face_service
            .get_single_face_embedding(
                image_bytes
            )
        )

    except ValueError as error:

        if str(error) == "NO_FACE":
            raise HTTPException(
                status_code=400,
                detail="ไม่พบใบหน้า",
            )

        if str(error) == "MULTIPLE_FACES":
            raise HTTPException(
                status_code=400,
                detail="ต้องมีเพียงหนึ่งใบหน้า",
            )

        raise

    face = FaceEmbedding(
        user_id=user.id,
        embedding=embedding.tolist(),
    )

    db.add(face)
    db.commit()

    return {
        "status": "success",
        "user_id": user.id,
        "name": user.name,
        "message": "บันทึก Face Embedding สำเร็จ",
    }