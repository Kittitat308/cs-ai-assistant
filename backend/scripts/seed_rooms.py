"""เพิ่มหรือปรับปรุงข้อมูลห้องของสาขาวิทยาการคอมพิวเตอร์"""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.room import Room  # noqa: E402


ROOMS = (
    (
        "ห้องปฏิบัติการคอมพิวเตอร์ 1 (Lab 1)",
        6,
        "ห้องปฏิบัติการคอมพิวเตอร์",
        "ตึก 60 ปี คณะวิทยาศาสตร์",
    ),
    (
        "ห้องปฏิบัติการคอมพิวเตอร์ 2 (Lab 2)",
        6,
        "ห้องปฏิบัติการคอมพิวเตอร์",
        "ตึก 60 ปี คณะวิทยาศาสตร์",
    ),
    (
        "ห้องปฏิบัติการคอมพิวเตอร์ 3 (Lab 3)",
        6,
        "ห้องปฏิบัติการคอมพิวเตอร์",
        "ตึก 60 ปี คณะวิทยาศาสตร์",
    ),
    (
        "ห้องปฏิบัติการคอมพิวเตอร์ 4 (Lab 4)",
        6,
        "ห้องปฏิบัติการคอมพิวเตอร์",
        "ตึก 60 ปี คณะวิทยาศาสตร์",
    ),
    (
        "ห้องปฏิบัติการเครือข่ายคอมพิวเตอร์ (Lab 5)",
        6,
        "ห้องปฏิบัติการเครือข่ายคอมพิวเตอร์",
        "ตึก 60 ปี คณะวิทยาศาสตร์",
    ),
    (
        "ห้องปฏิบัติการคอมพิวเตอร์ 5 (LabcomputerScience)",
        6,
        "ห้องปฏิบัติการคอมพิวเตอร์",
        "ตึก 60 ปี คณะวิทยาศาสตร์",
    ),
    (
        "ห้องบรรยายคอมพิวเตอร์ 6 (Lect 6)",
        2,
        "ห้องบรรยายคอมพิวเตอร์",
        "ตึก 60 ปี คณะวิทยาศาสตร์",
    ),
    (
        "ห้องบรรยายคอมพิวเตอร์ 8 (Lect 8)",
        2,
        "ห้องบรรยายคอมพิวเตอร์",
        "ตึก 60 ปี คณะวิทยาศาสตร์",
    ),
    (
        "ห้องคอมพิวเตอร์ 3203 จุฬาภรณ์",
        2,
        "ห้องบรรยายคอมพิวเตอร์",
        "อาคารจุฬาภรณ์ คณะวิทยาศาสตร์",
    ),
)


def seed_rooms() -> tuple[int, int]:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    created = 0
    updated = 0

    try:
        for name, floor, room_type, building in ROOMS:
            room = db.query(Room).filter(Room.name == name).first()

            if room is None:
                room = Room(name=name)
                db.add(room)
                created += 1
            else:
                updated += 1

            room.floor = floor
            room.room_type = room_type
            room.building = building

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return created, updated


if __name__ == "__main__":
    created_count, updated_count = seed_rooms()
    print(f"เพิ่มห้องใหม่ {created_count} ห้อง")
    print(f"ปรับปรุงห้องเดิม {updated_count} ห้อง")
