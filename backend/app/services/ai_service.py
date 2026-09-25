import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.services.conversation_session_service import (
    ConversationMessage,
    ConversationSession,
    conversation_session_service,
)
from app.services.tool_service import tool_service


logger = logging.getLogger(__name__)


class FunctionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AIResponse(BaseModel):
    """JSON contract เดียวที่ Gemini ต้องคืนในทุกครั้ง"""

    model_config = ConfigDict(extra="forbid")

    response: str
    functions: list[FunctionRequest]


class AIService:
    """จัดการ Gemini, conversation memory และ function-selection flow"""

    FALLBACK_RESPONSE = "ขออภัยครับ ระบบไม่สามารถประมวลผลคำตอบได้"

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
        self.client = genai.Client(api_key=settings.gemini_api_key)

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
        limit: int = 8,
    ) -> list[ConversationMessage]:
        """ดึงบทสนทนา 8 ข้อความล่าสุด (4 รอบ) จาก memory"""

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

        if parsed.functions:
            # เมื่อมี function ตาม contract ต้องยังไม่ตอบผู้ใช้
            parsed.response = ""

        return parsed

    @staticmethod
    def _build_system_prompt(
        identity: str,
        current_time: str,
    ) -> str:
        tool_catalog = json.dumps(
            tool_service.get_catalog(),
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return f"""
คุณคือ CS AI Assistant ประจำสาขาวิทยาการคอมพิวเตอร์

หน้าที่:
1. ตอบผู้ใช้โดยตรงเมื่อมีข้อมูลเพียงพอ
2. เลือก functions ที่ Backend ต้องเรียกเมื่อจำเป็นต้องใช้ข้อมูลเฉพาะ

กฎการตอบ:
- ตอบภาษาไทยเป็นหลัก และใช้ศัพท์เทคนิคภาษาอังกฤษได้
- ตอบสั้นและตรงคำถาม เหมาะกับ TTS โดยปกติ 1 ประโยค ไม่เกิน 2 ประโยค
- ห้ามเกริ่นนำ ทวนคำถาม หรือเสนอข้อมูลที่ไม่ได้ถาม
- เวลาทักทายหรือเรียกผู้ใช้ ให้พูดเฉพาะชื่อ ห้ามพูดรหัสประจำตัว
- ห้ามสร้างข้อมูลนักศึกษา อาจารย์ ตารางเรียน ห้อง หรือข้อมูลสาขาขึ้นเอง
- identity ต้องเชื่อ Backend เท่านั้น
- หากต้องใช้ข้อมูลที่ไม่ได้อยู่ใน prompt ให้เลือก function ที่เหมาะสม
- เลือก functions ที่จำเป็นทั้งหมดพร้อมกันในรอบแรกเมื่อไม่พึ่งผลลัพธ์กัน
- ห้ามเรียก function หากตอบได้จากความรู้ทั่วไป, identity, เวลา หรือ history
- เมื่อได้รับ function_results ต้องตอบจากผลเหล่านั้นเท่านั้น ห้ามขอ function เพิ่ม
- ถ้า function result ไม่มีข้อมูลหรือมี error ให้ตอบตามจริงโดยไม่เดา

กฎ JSON:
- Output ต้องเป็น JSON object เท่านั้น ห้ามมี Markdown หรือข้อความนอก JSON
- top-level ต้องมีเพียง response และ functions
- ถ้ามี functions ให้ response เป็น string ว่าง
- ถ้าพร้อมตอบ ให้ functions เป็น array ว่าง
- แต่ละ function มี name และ arguments เท่านั้น

functions ที่ Backend อนุญาต:
{tool_catalog}

{identity}

{current_time}
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
        """เรียก Gemini 1 ครั้ง หรือสูงสุด 2 ครั้งเมื่อจำเป็นต้องใช้ function"""

        self.remember_claimed_name(db, session, user_text)

        system_prompt = self._build_system_prompt(
            self.get_user_context(db, session),
            self.get_current_time_context(),
        )
        contents = self._build_contents(
            self.get_history(db, session),
            user_text,
        )

        first_response = await self._request_gemini(
            system_prompt,
            contents,
        )

        if first_response is None:
            return self.FALLBACK_RESPONSE

        if not first_response.functions:
            return first_response.response.strip() or self.FALLBACK_RESPONSE

        function_calls = [
            call.model_dump()
            for call in first_response.functions
        ]
        function_results = tool_service.execute_calls(
            db,
            session,
            function_calls,
        )

        second_contents = [
            *contents,
            types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=first_response.model_dump_json()
                    )
                ],
            ),
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=json.dumps(
                            {"function_results": function_results},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
                ],
            ),
        ]

        final_response = await self._request_gemini(
            system_prompt,
            second_contents,
        )

        if final_response is None:
            return self.FALLBACK_RESPONSE

        if final_response.functions:
            # ไม่สร้าง loop รอบที่สาม แม้โมเดลจะร้องขอเพิ่ม
            return (
                final_response.response.strip()
                or "ขออภัยครับ ไม่พบข้อมูลเพียงพอ"
            )

        return final_response.response.strip() or self.FALLBACK_RESPONSE


ai_service = AIService()
