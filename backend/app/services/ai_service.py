import asyncio
import re

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.conversation import ChatSession, Message, SessionProfile
from app.models.schedule import ClassSchedule
from app.models.user import User


class AIService:
    """
    จัดการ Gemini และ conversation memory
    """

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

    DAY_LABELS = {
        "monday": "วันจันทร์",
        "tuesday": "วันอังคาร",
        "wednesday": "วันพุธ",
        "thursday": "วันพฤหัสบดี",
        "friday": "วันศุกร์",
        "saturday": "วันเสาร์",
        "sunday": "วันอาทิตย์",
    }

    def __init__(self):
        # API key อยู่ใน backend/.env
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
        )

    @staticmethod
    def get_user_context(
        db: Session,
        session: ChatSession,
    ) -> str:
        """
        สร้างข้อมูล identity ให้ AI

        Gemini ไม่มีสิทธิ์ตัดสินเองว่าผู้ใช้เป็นใคร
        Backend เป็นผู้กำหนดจาก Face Recognition
        """

        if session.user_id is None:
            profile = db.get(
                SessionProfile,
                session.id,
            )

            if profile is not None:
                return f"""
ผู้ใช้ปัจจุบัน:
ชื่อที่ผู้ใช้แจ้ง: {profile.claimed_name}
สถานะ: guest
การยืนยันตัวตน: ชื่อนี้มาจากบทสนทนา ยังไม่ได้ยืนยันด้วยใบหน้า
ให้เรียกผู้ใช้ด้วยชื่อนี้และจำชื่อนี้ตลอด session ปัจจุบัน
"""

            return """
ผู้ใช้ปัจจุบัน:
ชื่อ: ไม่ทราบ
สถานะ: guest
การยืนยันตัวตน: ยังไม่ยืนยัน
"""

        user = db.get(
            User,
            session.user_id,
        )

        if user is None:
            return """
ผู้ใช้ปัจจุบัน:
ชื่อ: ไม่ทราบ
สถานะ: guest
"""

        schedules = (
            db.query(ClassSchedule)
            .filter(ClassSchedule.user_id == user.id)
            .order_by(
                ClassSchedule.course_code,
                ClassSchedule.meeting_index,
            )
            .all()
        )
        schedule_context = (
            "\n".join(
                f"- {AIService.DAY_LABELS.get(item.day_of_week, item.day_of_week)} "
                f"{item.course_code} {item.subject_name} "
                f"กลุ่ม {item.group_number}: "
                f"{item.start_time.strftime('%H:%M')}-"
                f"{item.end_time.strftime('%H:%M')}"
                for item in schedules
            )
            if schedules
            else "ไม่มีข้อมูลตารางเรียน"
        )

        return f"""
ผู้ใช้ปัจจุบัน:
ชื่อ: {user.name}
สถานะ: {user.role}
การยืนยันตัวตน: ยืนยันจากระบบ Face Recognition แล้ว
ตารางเรียน:
{schedule_context}
"""

    @classmethod
    def extract_claimed_name(
        cls,
        user_text: str,
    ) -> str | None:
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
        session: ChatSession,
        user_text: str,
    ) -> str | None:
        """จำชื่อที่ guest แจ้งไว้ใน session โดยยังไม่ถือว่ายืนยันตัวตน"""

        if session.user_id is not None:
            return None

        name = cls.extract_claimed_name(user_text)

        if name is None:
            return None

        profile = db.get(SessionProfile, session.id)

        if profile is None:
            profile = SessionProfile(
                session_id=session.id,
                claimed_name=name,
            )
            db.add(profile)
        else:
            profile.claimed_name = name

        db.flush()
        return name

    @staticmethod
    def get_history(
        db: Session,
        session_id: int,
        limit: int = 12,
    ):
        """
        ดึง conversation ล่าสุด

        จำกัดจำนวนข้อความเพื่อไม่ให้ prompt ใหญ่ขึ้นเรื่อย ๆ
        """

        messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.id.desc())
            .limit(limit)
            .all()
        )

        # query จากใหม่ → เก่า
        # จึงกลับลำดับให้เป็น เก่า → ใหม่
        return list(reversed(messages))

    async def generate_reply(
        self,
        db: Session,
        session: ChatSession,
        user_text: str,
    ) -> str:
        """
        สร้างคำตอบจาก Gemini
        """

        self.remember_claimed_name(
            db,
            session,
            user_text,
        )

        identity = self.get_user_context(
            db,
            session,
        )

        system_prompt = f"""
คุณคือ CS AI Assistant
เป็น AI Assistant ประจำสาขาวิทยาการคอมพิวเตอร์

กฎ:
- ตอบเป็นภาษาไทยเป็นหลัก
- ถ้าผู้ใช้ใช้ศัพท์เทคนิคภาษาอังกฤษ สามารถใช้ภาษาอังกฤษร่วมได้
- ตอบกระชับ เหมาะกับการอ่านข้อความออกเสียง
- อย่าใช้ Markdown ที่ซับซ้อน
- อย่าสร้างข้อมูลนักศึกษา อาจารย์ ตารางเรียน หรือข้อมูลส่วนตัวขึ้นเอง
- identity ของผู้ใช้ต้องเชื่อข้อมูลจาก Backend เท่านั้น
- หากไม่มีข้อมูล ให้บอกว่าไม่มีข้อมูล
- ผู้ใช้ guest ต้องไม่ได้รับข้อมูลส่วนบุคคลของนักศึกษาหรืออาจารย์
- เวลาทักทายหรือเรียกผู้ใช้ ให้พูดเฉพาะชื่อ ห้ามพูดรหัสนักศึกษาหรือรหัสประจำตัว

{identity}
"""

        history = self.get_history(
            db,
            session.id,
        )

        contents = []

        # แปลง conversation ใน database
        # เป็น Gemini conversation format
        for message in history:
            gemini_role = (
                "model"
                if message.role == "assistant"
                else "user"
            )

            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[
                        types.Part(
                            text=message.content
                        )
                    ],
                )
            )

        # เพิ่มข้อความใหม่
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=user_text
                    )
                ],
            )
        )

        def _generate():
            response = self.client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.4,
                    automatic_function_calling=(
                        types.AutomaticFunctionCallingConfig(
                            disable=True,
                        )
                    ),
                ),
            )

            return (
                response.text.strip()
                if response.text
                else "ขออภัยครับ ผมไม่สามารถสร้างคำตอบได้"
            )

        return await asyncio.to_thread(
            _generate
        )


ai_service = AIService()
