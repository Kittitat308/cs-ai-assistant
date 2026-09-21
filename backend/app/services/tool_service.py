import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.conversation import ChatSession
from app.models.lecturer import LecturerProfile
from app.models.room import Room
from app.models.schedule import ClassSchedule
from app.models.user import User


class ScheduleArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str | None = None


class LecturerArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=255)


class RoomArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(default="", max_length=255)


class DepartmentDataArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)


class ToolService:
    """Whitelist ของ functions ที่ Gemini สามารถขอให้ Backend เรียกได้"""

    DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data"

    DAY_LABELS = {
        "monday": "วันจันทร์",
        "tuesday": "วันอังคาร",
        "wednesday": "วันพุธ",
        "thursday": "วันพฤหัสบดี",
        "friday": "วันศุกร์",
        "saturday": "วันเสาร์",
        "sunday": "วันอาทิตย์",
    }

    TOOL_CATALOG = [
        {
            "name": "get_my_schedule",
            "description": (
                "ดูตารางเรียนของผู้ใช้ที่ยืนยันตัวตนแล้วในวันที่ระบุ "
                "คืนวิชา กลุ่ม วัน เวลา และห้องจากฐานข้อมูล"
            ),
            "arguments": {
                "date": (
                    "วันที่รูปแบบ YYYY-MM-DD; ไม่ส่งค่านี้เมื่อต้องการวันนี้"
                ),
            },
        },
        {
            "name": "get_lecturer_info",
            "description": (
                "ค้นข้อมูลสาธารณะของอาจารย์ เช่น ชื่อ ตำแหน่ง "
                "การศึกษา โทรศัพท์ และอีเมล"
            ),
            "arguments": {
                "name": (
                    "ชื่อหรือบางส่วนของชื่อ; ใช้ string ว่างเฉพาะเมื่อผู้ใช้ถามรายชื่อทั้งหมด"
                ),
            },
        },
        {
            "name": "get_room_info",
            "description": (
                "ค้นห้องจากชื่อห้อง อาคาร หรือประเภทห้อง "
                "คืนชื่อ ชั้น ประเภท และอาคาร"
            ),
            "arguments": {
                "query": (
                    "คำค้น; ใช้ string ว่างเฉพาะเมื่อผู้ใช้ถามห้องทั้งหมด"
                ),
            },
        },
        {
            "name": "search_department_data",
            "description": (
                "ค้นข้อมูลสาขาจากไฟล์ Markdown/Text ใน backend/data "
                "เช่น ประวัติ ที่ตั้ง และข้อมูลติดต่อ"
            ),
            "arguments": {
                "query": "ข้อความที่ต้องการค้นหา",
            },
        },
    ]

    def get_catalog(self) -> list[dict[str, Any]]:
        """คืนเฉพาะ metadata ของ functions โดยไม่อ่าน Database หรือไฟล์ข้อมูล"""

        return self.TOOL_CATALOG

    def execute_calls(
        self,
        db: Session,
        session: ChatSession,
        calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Validate และเรียกเฉพาะ function ที่อยู่ใน whitelist"""

        handlers = {
            "get_my_schedule": self._get_my_schedule,
            "get_lecturer_info": self._get_lecturer_info,
            "get_room_info": self._get_room_info,
            "search_department_data": self._search_department_data,
        }
        results = []

        # จำกัดจำนวน calls เพื่อป้องกัน output จากโมเดลที่ผิดปกติ
        for call in calls[:8]:
            name = call.get("name")
            arguments = call.get("arguments")
            handler = handlers.get(name)

            if handler is None:
                results.append(
                    {
                        "name": str(name or ""),
                        "result": {"error": "function_not_allowed"},
                    }
                )
                continue

            if not isinstance(arguments, dict):
                results.append(
                    {
                        "name": name,
                        "result": {"error": "invalid_arguments"},
                    }
                )
                continue

            try:
                result = handler(db, session, arguments)
            except ValidationError:
                result = {"error": "invalid_arguments"}
            except Exception:
                # ไม่ส่งรายละเอียด exception, SQL หรือข้อมูลระบบให้ Gemini
                result = {"error": "function_failed"}

            results.append({"name": name, "result": result})

        return results

    def _get_my_schedule(
        self,
        db: Session,
        session: ChatSession,
        raw_arguments: dict[str, Any],
    ) -> dict[str, Any]:
        arguments = ScheduleArguments.model_validate(raw_arguments)

        if session.user_id is None:
            return {"error": "permission_denied", "items": []}

        user = db.get(User, session.user_id)

        if user is None or not user.is_active:
            return {"error": "user_not_found", "items": []}

        if arguments.date:
            try:
                target_date = date.fromisoformat(arguments.date)
            except ValueError:
                return {"error": "invalid_date", "items": []}
        else:
            target_date = datetime.now(ZoneInfo("Asia/Bangkok")).date()

        day_key = target_date.strftime("%A").lower()
        schedules = (
            db.query(ClassSchedule)
            .options(joinedload(ClassSchedule.room))
            .filter(
                ClassSchedule.user_id == user.id,
                ClassSchedule.day_of_week == day_key,
            )
            .order_by(
                ClassSchedule.start_time,
                ClassSchedule.course_code,
                ClassSchedule.meeting_index,
            )
            .all()
        )

        return {
            "date": target_date.isoformat(),
            "day": self.DAY_LABELS.get(day_key, day_key),
            "items": [
                {
                    "course_code": item.course_code,
                    "subject_name": item.subject_name,
                    "group_number": item.group_number,
                    "meeting_index": item.meeting_index,
                    "start_time": item.start_time.strftime("%H:%M"),
                    "end_time": item.end_time.strftime("%H:%M"),
                    "room": (
                        {
                            "name": item.room.name,
                            "floor": item.room.floor,
                            "room_type": item.room.room_type,
                            "building": item.room.building,
                        }
                        if item.room is not None
                        else None
                    ),
                }
                for item in schedules
            ],
        }

    @staticmethod
    def _get_lecturer_info(
        db: Session,
        _session: ChatSession,
        raw_arguments: dict[str, Any],
    ) -> dict[str, Any]:
        arguments = LecturerArguments.model_validate(raw_arguments)
        name = " ".join(arguments.name.strip().split())

        query = (
            db.query(User, LecturerProfile)
            .outerjoin(
                LecturerProfile,
                LecturerProfile.user_id == User.id,
            )
            .filter(
                User.role == "lecturer",
                User.is_active.is_(True),
            )
        )

        if name:
            query = query.filter(User.name.ilike(f"%{name}%"))

        rows = query.order_by(User.name).limit(20).all()

        return {
            "items": [
                {
                    "name": user.name,
                    "academic_title": (
                        profile.academic_title if profile else None
                    ),
                    "position": profile.position if profile else None,
                    "education": profile.education if profile else None,
                    "phone": profile.phone if profile else None,
                    "email": profile.email if profile else None,
                }
                for user, profile in rows
            ]
        }

    @staticmethod
    def _get_room_info(
        db: Session,
        _session: ChatSession,
        raw_arguments: dict[str, Any],
    ) -> dict[str, Any]:
        arguments = RoomArguments.model_validate(raw_arguments)
        search_text = " ".join(arguments.query.strip().split())
        query = db.query(Room)

        if search_text:
            pattern = f"%{search_text}%"
            query = query.filter(
                or_(
                    Room.name.ilike(pattern),
                    Room.building.ilike(pattern),
                    Room.room_type.ilike(pattern),
                )
            )

        rooms = (
            query.order_by(Room.building, Room.floor, Room.name)
            .limit(30)
            .all()
        )

        return {
            "items": [
                {
                    "name": room.name,
                    "floor": room.floor,
                    "room_type": room.room_type,
                    "building": room.building,
                }
                for room in rooms
            ]
        }

    def _search_department_data(
        self,
        _db: Session,
        _session: ChatSession,
        raw_arguments: dict[str, Any],
    ) -> dict[str, Any]:
        arguments = DepartmentDataArguments.model_validate(raw_arguments)
        query = self._normalize_text(arguments.query)

        if not self.DATA_DIRECTORY.exists():
            return {"items": []}

        candidates = []

        for path in sorted(self.DATA_DIRECTORY.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for section in self._split_sections(content):
                score = self._relevance_score(query, section)

                if score <= 0:
                    continue

                candidates.append(
                    (
                        score,
                        path.relative_to(self.DATA_DIRECTORY).as_posix(),
                        section.strip(),
                    )
                )

        candidates.sort(key=lambda item: item[0], reverse=True)
        selected = []
        total_characters = 0

        for _score, source, section in candidates[:6]:
            excerpt = section[:1600].strip()

            if total_characters + len(excerpt) > 4000:
                remaining = 4000 - total_characters
                excerpt = excerpt[:remaining].strip()

            if not excerpt:
                break

            selected.append({"source": source, "content": excerpt})
            total_characters += len(excerpt)

            if len(selected) >= 3 or total_characters >= 4000:
                break

        return {"items": selected}

    @staticmethod
    def _split_sections(content: str) -> list[str]:
        sections = re.split(
            r"(?=^#{1,6}\s+)",
            content,
            flags=re.MULTILINE,
        )

        if len(sections) <= 1:
            sections = re.split(r"\n\s*\n", content)

        return [section for section in sections if section.strip()]

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", "", value.casefold())

    @classmethod
    def _relevance_score(cls, query: str, section: str) -> float:
        normalized_section = cls._normalize_text(section)

        if not query or not normalized_section:
            return 0

        score = 0.0

        if query in normalized_section:
            score += 100.0

        words = re.findall(r"[\w\u0E00-\u0E7F]+", query)
        score += sum(
            normalized_section.count(word) * 10.0
            for word in words
            if len(word) >= 2
        )

        query_grams = {
            query[index:index + 3]
            for index in range(max(0, len(query) - 2))
        }

        if query_grams:
            matching_grams = sum(
                gram in normalized_section
                for gram in query_grams
            )
            score += (matching_grams / len(query_grams)) * 30.0

        return score


tool_service = ToolService()
