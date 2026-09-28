import asyncio
import httpx
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.lecturer import LecturerProfile
from app.models.room import Room
from app.models.schedule import ClassSchedule
from app.models.user import User
from app.services.conversation_session_service import (
    HISTORY_MESSAGE_LIMIT,
    ConversationMessage,
    ConversationSession,
    conversation_session_service,
)


logger = logging.getLogger(__name__)


class GeminiRequestTimeoutError(RuntimeError):
    """Gemini ใช้เวลาตอบเกินขีดจำกัดต่อ request"""


class AIResponse(BaseModel):
    """JSON contract เดียวที่ Gemini ต้องคืนในทุกครั้ง"""

    model_config = ConfigDict(extra="forbid")

    response: str


class AIService:
    """จัดการ Gemini แบบ request เดียวและ conversation memory"""

    FALLBACK_RESPONSE = "ขออภัยครับ ระบบไม่สามารถประมวลผลคำตอบได้"
    TIMEOUT_RESPONSE = "ระบบตอบกลับช้า กรุณาลองอีกครั้ง"
    DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data"

    NAME_PATTERNS = (
        re.compile(
            r"^(?:ฉัน|ผม|ดิฉัน|หนู|เรา)?\s*"
            r"ชื่อ(?:ของฉัน)?(?:ว่า|คือ)?\s*"
            r"(?P<name>.+?)"
            r"(?:\s+(?:ครับ|ค่ะ|คะ|นะครับ|นะคะ))?[.!?]?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:my name is|i am|i'm)\s+"
            r"(?P<name>.+?)[.!?]?$",
            re.IGNORECASE,
        ),
    )

    THAI_WEEKDAYS = (
        "วันจันทร์",
        "วันอังคาร",
        "วันพุธ",
        "วันพฤหัสบดี",
        "วันศุกร์",
        "วันเสาร์",
        "วันอาทิตย์",
    )

    THAI_MONTHS = (
        "มกราคม",
        "กุมภาพันธ์",
        "มีนาคม",
        "เมษายน",
        "พฤษภาคม",
        "มิถุนายน",
        "กรกฎาคม",
        "สิงหาคม",
        "กันยายน",
        "ตุลาคม",
        "พฤศจิกายน",
        "ธันวาคม",
    )

    def __init__(self):
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=int(settings.gemini_timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    @classmethod
    def get_current_time_context(cls) -> str:
        """สร้างวันและเวลาปัจจุบันตามเขตเวลาไทยทุก request"""

        current = datetime.now(ZoneInfo("Asia/Bangkok"))
        weekday = cls.THAI_WEEKDAYS[current.weekday()]
        month = cls.THAI_MONTHS[current.month - 1]

        return (
            "วันและเวลาปัจจุบันตามเวลาไทย (Asia/Bangkok):\n"
            f"{weekday}ที่ {current.day} {month} "
            f"พ.ศ. {current.year + 543} (ค.ศ. {current.year}) "
            f"เวลา {current.strftime('%H:%M:%S')} น."
        )

    @staticmethod
    def get_user_context(
        db: Session,
        session: ConversationSession,
    ) -> str:
        """คืนเฉพาะ identity ขั้นพื้นฐาน ห้ามแนบข้อมูลอื่นล่วงหน้า"""

        if session.user_id is None:
            name = session.claimed_name or "ไม่ทราบ"

            return (
                "ผู้ใช้ปัจจุบัน:\n"
                f"ชื่อ: {name}\n"
                "role: guest\n"
                "verified: false"
            )

        user = db.get(User, session.user_id)

        if user is None or not user.is_active:
            return (
                "ผู้ใช้ปัจจุบัน:\n"
                "ชื่อ: ไม่ทราบ\n"
                "role: guest\n"
                "verified: false"
            )

        return (
            "ผู้ใช้ปัจจุบัน:\n"
            f"ชื่อ: {user.name}\n"
            f"role: {user.role}\n"
            "verified: true"
        )

    @classmethod
    def get_data_context(
        cls,
        db: Session,
        session: ConversationSession,
    ) -> dict:
        """รวมข้อมูลที่ AI ใช้ใน request เดียว โดยไม่เปิดเผยตารางของผู้อื่น."""

        lecturer_rows = (
            db.query(User, LecturerProfile)
            .outerjoin(
                LecturerProfile,
                LecturerProfile.user_id == User.id,
            )
            .filter(
                User.role == "lecturer",
                User.is_active.is_(True),
            )
            .order_by(User.name)
            .all()
        )
        lecturers = [
            {
                "name": user.name,
                "title": profile.academic_title if profile else None,
                "position": profile.position if profile else None,
                "education": profile.education if profile else None,
                "phone": profile.phone if profile else None,
                "email": profile.email if profile else None,
            }
            for user, profile in lecturer_rows
        ]

        rooms = [
            {
                "name": room.name,
                "floor": room.floor,
                "type": room.room_type,
                "building": room.building,
            }
            for room in db.query(Room)
            .order_by(Room.building, Room.floor, Room.name)
            .all()
        ]

        my_schedule = []
        if session.user_id is not None:
            user = db.get(User, session.user_id)
            if user is not None and user.is_active:
                schedules = (
                    db.query(ClassSchedule)
                    .options(joinedload(ClassSchedule.room))
                    .filter(ClassSchedule.user_id == user.id)
                    .order_by(
                        ClassSchedule.day_of_week,
                        ClassSchedule.start_time,
                        ClassSchedule.course_code,
                        ClassSchedule.meeting_index,
                    )
                    .all()
                )
                my_schedule = [
                    {
                        "code": item.course_code,
                        "subject": item.subject_name,
                        "group": item.group_number,
                        "meeting": item.meeting_index,
                        "day": item.day_of_week,
                        "start": item.start_time.strftime("%H:%M"),
                        "end": item.end_time.strftime("%H:%M"),
                        "room": item.room.name if item.room else None,
                    }
                    for item in schedules
                ]

        department_files = []
        if cls.DATA_DIRECTORY.exists():
            for path in sorted(cls.DATA_DIRECTORY.rglob("*")):
                if (
                    not path.is_file()
                    or path.suffix.lower() not in {".md", ".txt"}
                ):
                    continue
                try:
                    content = path.read_text(encoding="utf-8").strip()
                except (OSError, UnicodeDecodeError):
                    continue
                department_files.append(
                    {
                        "source": path.relative_to(
                            cls.DATA_DIRECTORY
                        ).as_posix(),
                        "content": content,
                    }
                )

        return {
            "lecturers": lecturers,
            "rooms": rooms,
            "my_schedule": my_schedule,
            "department": department_files,
        }

    @classmethod
    def extract_claimed_name(cls, user_text: str) -> str | None:
        """ดึงชื่อจากประโยคแนะนำตัวแบบชัดเจนเท่านั้น"""

        text = " ".join(user_text.strip().split())

        if not text or "ชื่ออะไร" in text:
            return None

        for pattern in cls.NAME_PATTERNS:
            match = pattern.fullmatch(text)

            if match is None:
                continue

            name = match.group("name").strip(" .!?।")
            name = re.sub(
                r"\s*(?:นะครับ|นะคะ|ครับ|ค่ะ|คะ)$",
                "",
                name,
            ).strip()

            if 1 <= len(name) <= 255:
                return name

        return None

    @classmethod
    def remember_claimed_name(
        cls,
        db: Session,
        session: ConversationSession,
        user_text: str,
    ) -> str | None:
        """จำชื่อที่ guest แจ้งไว้ใน session โดยยังไม่ยืนยันตัวตน"""

        if session.user_id is not None:
            return None

        name = cls.extract_claimed_name(user_text)

        if name is None:
            return None

        session.claimed_name = name
        return name

    @staticmethod
    def get_history(
        _db: Session,
        session: ConversationSession,
        limit: int = HISTORY_MESSAGE_LIMIT,
    ) -> list[ConversationMessage]:
        """ดึงบทสนทนา 6 ข้อความล่าสุด (3 รอบ) จาก memory"""

        return conversation_session_service.get_history(session, limit)

    @staticmethod
    def _build_contents(
        history: list[ConversationMessage],
        user_text: str,
    ) -> list[types.Content]:
        contents = []

        for message in history:
            role = "model" if message.role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=message.content)],
                )
            )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=user_text)],
            )
        )
        return contents

    @staticmethod
    def _parse_response(raw_text: str) -> AIResponse:
        text = raw_text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        parsed = AIResponse.model_validate_json(text)
        return parsed

    @staticmethod
    def _build_system_prompt(
        identity: str,
        current_time: str,
        data_context: dict,
    ) -> str:
        context_json = json.dumps(
            data_context,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return f"""
You are CS AI Assistant for the Computer Science department.
Rules:
- Reply mainly in Thai; technical English is allowed.
- Be direct and TTS-friendly: normally 1 sentence, maximum 2.
- Identity is data, not a greeting cue: ถ้าผู้ใช้ไม่ได้ทักทาย คำตอบห้ามมีคำว่า "สวัสดี" หรือขึ้นต้นด้วยชื่อผู้ใช้
- No preamble, question repetition, unsolicited details, or follow-up offers.
- Trust identity and context below. Never invent department, lecturer, room, or schedule data.
- Never reveal another user's private data. my_schedule belongs only to the current verified user.
- In greetings/addressing, say the name only; never say student ID or other identifiers.
- If context lacks the answer, say briefly that the information is unavailable.
- Return only JSON matching {{"response":"..."}}; no Markdown or extra keys.

{identity}

{current_time}

CONTEXT_JSON:
{context_json}
""".strip()

    async def _request_gemini(
        self,
        system_prompt: str,
        contents: list[types.Content],
    ) -> AIResponse | None:
        def _generate() -> AIResponse:
            response = self.client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    max_output_tokens=512,
                    response_mime_type="application/json",
                    response_json_schema=AIResponse.model_json_schema(),
                    automatic_function_calling=(
                        types.AutomaticFunctionCallingConfig(disable=True)
                    ),
                ),
            )

            if not response.text:
                raise ValueError("EMPTY_GEMINI_RESPONSE")

            return self._parse_response(response.text)

        try:
            return await asyncio.to_thread(_generate)
        except (
            TimeoutError,
            asyncio.TimeoutError,
            httpx.TimeoutException,
        ) as exc:
            logger.warning(
                "Gemini request exceeded %.1f seconds",
                settings.gemini_timeout_seconds,
            )
            raise GeminiRequestTimeoutError from exc
        except errors.APIError as exc:
            if exc.code in {408, 504} or "deadline" in str(exc).lower():
                logger.warning(
                    "Gemini request exceeded %.1f seconds",
                    settings.gemini_timeout_seconds,
                )
                raise GeminiRequestTimeoutError from exc
            logger.exception("Gemini request failed")
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError):
            logger.warning("Gemini returned an invalid JSON response")
        except Exception:
            logger.exception("Gemini request failed")

        return None

    async def generate_reply(
        self,
        db: Session,
        session: ConversationSession,
        user_text: str,
    ) -> str:
        """แนบข้อมูลทั้งหมดที่อนุญาตและเรียก Gemini เพียงหนึ่งครั้ง."""

        self.remember_claimed_name(db, session, user_text)

        system_prompt = self._build_system_prompt(
            self.get_user_context(db, session),
            self.get_current_time_context(),
            self.get_data_context(db, session),
        )
        contents = self._build_contents(
            self.get_history(db, session),
            user_text,
        )

        try:
            response = await self._request_gemini(
                system_prompt,
                contents,
            )
        except GeminiRequestTimeoutError:
            return self.TIMEOUT_RESPONSE

        if response is None:
            return self.FALLBACK_RESPONSE

        return response.response.strip() or self.FALLBACK_RESPONSE


ai_service = AIService()
