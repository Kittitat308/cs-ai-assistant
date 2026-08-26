import json
from datetime import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.face import FaceEmbedding
from app.models.schedule import ClassSchedule
from app.models.user import User
from app.services.face_service import face_service


router = APIRouter(
    prefix="/api/registration",
    tags=["Registration"],
)

ALLOWED_ROLES = {"lecturer", "student", "guest"}
ALLOWED_DAYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}


def parse_schedules(raw_schedules: str) -> list[dict]:
    try:
        schedules = json.loads(raw_schedules)
    except json.JSONDecodeError:
        raise HTTPException(400, "ข้อมูลตารางเรียนไม่ถูกต้อง")

    if not isinstance(schedules, list) or len(schedules) > 30:
        raise HTTPException(400, "ข้อมูลตารางเรียนไม่ถูกต้อง")

    parsed = []

    for item in schedules:
        if not isinstance(item, dict):
            raise HTTPException(400, "ข้อมูลตารางเรียนไม่ถูกต้อง")

        course_code = " ".join(
            str(item.get("course_code", "")).strip().split()
        )
        subject_name = " ".join(
            str(item.get("subject_name", "")).strip().split()
        )

        try:
            group_number = int(item.get("group_number", 0))
            meeting_count = int(item.get("meeting_count", 0))
        except (TypeError, ValueError):
            raise HTTPException(400, "กลุ่มและจำนวนครั้งที่เรียนต้องเป็นตัวเลข")

        meetings = item.get("meetings")

        if not course_code or len(course_code) > 50:
            raise HTTPException(400, "กรุณาป้อนรหัสวิชาให้ครบ")

        if not subject_name or len(subject_name) > 255:
            raise HTTPException(400, "กรุณาป้อนชื่อวิชาให้ครบ")

        if group_number < 1:
            raise HTTPException(400, "กรุณาป้อนกลุ่มให้ถูกต้อง")

        if not 1 <= meeting_count <= 30:
            raise HTTPException(400, "จำนวนครั้งที่เรียนไม่ถูกต้อง")

        if not isinstance(meetings, list) or len(meetings) != meeting_count:
            raise HTTPException(400, "จำนวนช่วงเรียนไม่ตรงกับจำนวนครั้งที่เรียน")

        for meeting_index, meeting in enumerate(meetings, start=1):
            if not isinstance(meeting, dict):
                raise HTTPException(400, "ข้อมูลช่วงเรียนไม่ถูกต้อง")

            day_of_week = str(
                meeting.get("day_of_week", "")
            ).strip().lower()
            start_value = str(meeting.get("start_time", ""))
            end_value = str(meeting.get("end_time", ""))

            if day_of_week not in ALLOWED_DAYS:
                raise HTTPException(400, "กรุณาเลือกวันเรียนให้ครบ")

            try:
                start_time = time.fromisoformat(start_value)
                end_time = time.fromisoformat(end_value)
            except ValueError:
                raise HTTPException(400, "กรุณาป้อนเวลาเรียนและเวลาเลิกให้ครบ")

            if end_time <= start_time:
                raise HTTPException(400, "เวลาเลิกต้องอยู่หลังเวลาเริ่มเรียน")

            parsed.append(
                {
                    "course_code": course_code,
                    "subject_name": subject_name,
                    "group_number": group_number,
                    "meeting_index": meeting_index,
                    "day_of_week": day_of_week,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )

    return parsed


@router.get("/student-id/{student_id}/availability")
def check_student_id_availability(
    student_id: str,
    db: Session = Depends(get_db),
):
    if len(student_id) != 10 or not student_id.isdigit():
        return {"available": False, "valid": False}

    exists = (
        db.query(User.id)
        .filter(User.external_id == student_id)
        .first()
        is not None
    )

    return {"available": not exists, "valid": True}


@router.post("")
async def register_user(
    name: str = Form(...),
    external_id: str = Form(""),
    role: str = Form(...),
    schedules: str = Form("[]"),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """ตรวจทุกขั้นตอนก่อนบันทึก user และ face embedding พร้อมกัน"""

    clean_name = " ".join(name.strip().split())

    if not clean_name:
        raise HTTPException(400, "กรุณาป้อนชื่อและนามสกุล")

    if len(clean_name) > 255:
        raise HTTPException(400, "ชื่อต้องยาวไม่เกิน 255 ตัวอักษร")

    if role not in ALLOWED_ROLES:
        raise HTTPException(400, "สถานะผู้ใช้ไม่ถูกต้อง")

    clean_external_id = external_id.strip()

    if role == "student":
        if len(clean_external_id) != 10 or not clean_external_id.isdigit():
            raise HTTPException(400, "รหัสนักศึกษาต้องเป็นตัวเลข 10 หลัก")
    else:
        clean_external_id = None

    parsed_schedules = parse_schedules(schedules)

    existing = None

    if clean_external_id is not None:
        existing = (
            db.query(User)
            .filter(User.external_id == clean_external_id)
            .first()
        )

    if existing is not None:
        raise HTTPException(409, "รหัสนักศึกษานี้ถูกใช้งานไปแล้ว")

    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(400, "กรุณาสแกนใบหน้า")

    try:
        embedding = face_service.get_single_face_embedding(image_bytes)
    except ValueError as error:
        error_code = str(error)

        if error_code == "NO_FACE":
            raise HTTPException(400, "ไม่พบใบหน้า กรุณาสแกนใหม่")

        if error_code == "MULTIPLE_FACES":
            raise HTTPException(400, "ต้องมีเพียงหนึ่งใบหน้าในภาพ")

        raise HTTPException(400, "ไม่สามารถอ่านภาพใบหน้าได้")

    try:
        user = User(
            external_id=clean_external_id,
            name=clean_name,
            role=role,
        )
        db.add(user)
        db.flush()

        db.add(
            FaceEmbedding(
                user_id=user.id,
                embedding=embedding.tolist(),
            )
        )

        for schedule in parsed_schedules:
            db.add(
                ClassSchedule(
                    user_id=user.id,
                    **schedule,
                )
            )

        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "รหัสนักศึกษานี้ถูกใช้งานไปแล้ว")
    except Exception:
        db.rollback()
        raise

    return {
        "status": "success",
        "user": {
            "id": user.id,
            "external_id": user.external_id,
            "name": user.name,
            "role": user.role,
        },
        "schedule_count": len(parsed_schedules),
    }
