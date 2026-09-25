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

    student_id = data.student_id.strip() if data.student_id else None
    email = data.email.strip().lower() if data.email else None

    if data.role == "student":
        if student_id is None or len(student_id) != 10 or not student_id.isdigit():
            raise HTTPException(400, "รหัสนักศึกษาต้องเป็นตัวเลข 10 หลัก")
    elif student_id is not None:
        raise HTTPException(400, "กำหนดรหัสนักศึกษาได้เฉพาะ role student")

    if email is not None and "@" not in email:
        raise HTTPException(400, "อีเมลไม่ถูกต้อง")

    existing = None

    if student_id is not None:
        existing = db.query(User).filter(User.student_id == student_id).first()

    if existing is None and email is not None:
        existing = db.query(User).filter(User.email == email).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="รหัสนี้มีอยู่แล้ว",
        )

    user = User(
        student_id=student_id,
        email=email,
        name=data.name,
        role=data.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "student_id": user.student_id,
        "email": user.email,
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
