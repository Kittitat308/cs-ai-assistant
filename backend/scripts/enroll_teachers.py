"""นำเข้าข้อมูลและใบหน้าอาจารย์จากโฟลเดอร์รูปแบบ transaction เดียว"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import or_


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.face import FaceEmbedding  # noqa: E402
from app.models.lecturer import LecturerProfile  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.face_service import face_service  # noqa: E402


@dataclass(frozen=True)
class TeacherRecord:
    filename: str
    email: str
    name: str
    academic_title: str
    position: str
    education: str
    phone: str


TEACHERS = (
    TeacherRecord(
        "Somnuek.png", "somnuek@mju.ac.th", "สมนึก สินธุปวน", "ผศ.ดร.",
        "ผู้ช่วยศาสตราจารย์",
        "ปร.ด.(วิทยาการคอมพิวเตอร์) หลักสูตรนานาชาติ สถาบันบัณฑิตพัฒนบริหารศาสตร์",
        "053-873890-93 ต่อ 24",
    ),
    TeacherRecord(
        "Snit Sitti.png", "snit@mju.ac.th", "สนิต สิทธิ", "ผศ.ดร.",
        "ผู้ช่วยศาสตราจารย์",
        "ศษ.ด.(เทคโนโลยีการศึกษา) มหาวิทยาลัยเกษตรศาสตร์",
        "053-873890-93 ต่อ 15",
    ),
    TeacherRecord(
        "Kongkarn Dullayachai.png", "kongkarn@mju.ac.th",
        "ก่องกาญจน์ ดุลยไชย", "ผศ.", "ผู้ช่วยศาสตราจารย์",
        "วท.ม.(วิทยาการคอมพิวเตอร์) สถาบันบัณฑิตพัฒนบริหารศาสตร์",
        "053-873890-93 ต่อ 14",
    ),
    TeacherRecord(
        "Alongkot Gongmanee.png", "alongkot@mju.ac.th", "อลงกต กองมณี", "อ.",
        "อาจารย์",
        "M.S.(Information Systems Management) Ferris State University, U.S.A.",
        "053-873890-93 ต่อ 22",
    ),
    TeacherRecord(
        "Kittikorn Hantrakul.png", "kittikor@mju.ac.th", "กิตติกร หาญตระกูล",
        "อ.ดร.", "อาจารย์", "ปร.ด.(การบริหารเทคโนโลยี) มหาวิทยาลัยแม่โจ้",
        "053-873890-93 ต่อ 21",
    ),
    TeacherRecord(
        "Attawit Changkamanon.png", "attawit@mju.ac.th", "อรรถวิท ชังคมานนท์",
        "อ.", "อาจารย์", "วท.ม.(วิทยาการคอมพิวเตอร์) มหาวิทยาลัยเชียงใหม่",
        "053-873890-93 ต่อ 13",
    ),
    TeacherRecord(
        "Panuwat Mekha.png", "panuwat_m@mju.ac.th", "ภานุวัฒน์ เมฆะ", "ผศ.",
        "ผู้ช่วยศาสตราจารย์", "วท.ม.(วิทยาการคอมพิวเตอร์) มหาวิทยาลัยเชียงใหม่",
        "053-873890-93 ต่อ 20",
    ),
    TeacherRecord(
        "Part Pramokchon.png", "part@mju.ac.th", "พจน์ ปราโมกข์ชน", "ผศ.ดร.",
        "ผู้ช่วยศาสตราจารย์", "วศ.ด.(วิศวกรรมคอมพิวเตอร์) มหาวิทยาลัยเกษตรศาสตร์",
        "053-873890-93 ต่อ 16",
    ),
    TeacherRecord(
        "Paween Khoenkaw.png", "paween_k@mju.ac.th", "ปวีณ เขื่อนแก้ว", "ผศ.ดร.",
        "ผู้ช่วยศาสตราจารย์", "วศ.ด.(วิศวกรรมคอมพิวเตอร์) มหาวิทยาลัยเกษตรศาสตร์",
        "053-873896",
    ),
    TeacherRecord(
        "Payungsak Kasemsumran.png", "payungsak_kae@mju.ac.th",
        "พยุงศักดิ์ เกษมสำราญ", "อ.ดร.", "อาจารย์",
        "ปร.ด.(วิศวกรรมคอมพิวเตอร์) มหาวิทยาลัยเชียงใหม่",
        "053-873890-93 ต่อ 17",
    ),
)


def prepare_faces(
    image_directory: Path,
) -> list[tuple[TeacherRecord, list[float]]]:
    """อ่านและตรวจทุกภาพก่อนเริ่มเปลี่ยนแปลงฐานข้อมูล"""

    prepared = []

    for teacher in TEACHERS:
        image_path = image_directory / teacher.filename

        if not image_path.is_file():
            raise FileNotFoundError(f"ไม่พบไฟล์รูป: {image_path}")

        embedding = face_service.get_single_face_embedding(image_path.read_bytes())
        prepared.append((teacher, embedding.tolist()))

    return prepared


def enroll_teachers(image_directory: Path) -> tuple[list[str], list[str]]:
    prepared = prepare_faces(image_directory)
    Base.metadata.create_all(bind=engine)
    created = []
    updated = []
    db = SessionLocal()

    try:
        for teacher, embedding in prepared:
            user = (
                db.query(User)
                .filter(or_(User.email == teacher.email, User.name == teacher.name))
                .first()
            )

            if user is None:
                user = User(
                    email=teacher.email,
                    name=teacher.name,
                    role="lecturer",
                )
                db.add(user)
                db.flush()
                created.append(teacher.name)
            else:
                user.email = teacher.email
                user.name = teacher.name
                user.role = "lecturer"
                updated.append(teacher.name)

            has_face = (
                db.query(FaceEmbedding.id)
                .filter(FaceEmbedding.user_id == user.id)
                .first()
                is not None
            )

            if not has_face:
                db.add(FaceEmbedding(user_id=user.id, embedding=embedding))

            profile = (
                db.query(LecturerProfile)
                .filter(LecturerProfile.user_id == user.id)
                .first()
            )

            if profile is None:
                profile = LecturerProfile(user_id=user.id)
                db.add(profile)

            profile.academic_title = teacher.academic_title
            profile.position = teacher.position
            profile.education = teacher.education
            profile.phone = teacher.phone
            profile.email = teacher.email

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return created, updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "image_directory",
        type=Path,
        help="โฟลเดอร์ที่เก็บรูปอาจารย์ตามชื่อไฟล์ที่กำหนด",
    )
    args = parser.parse_args()

    created, updated = enroll_teachers(args.image_directory.resolve())
    print(f"เพิ่มอาจารย์ใหม่ {len(created)} คน")

    for name in created:
        print(f"  + {name}")

    print(f"ปรับปรุงข้อมูลที่มีอยู่แล้ว {len(updated)} คน")

    for name in updated:
        print(f"  = {name}")


if __name__ == "__main__":
    main()
