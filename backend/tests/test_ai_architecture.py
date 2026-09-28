import asyncio
import os
import unittest
from types import SimpleNamespace

from pydantic import ValidationError


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost/test",
)
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("ADMIN_TOKEN", "test")


from app.services.ai_service import (  # noqa: E402
    AIResponse,
    AIService,
    GeminiRequestTimeoutError,
)
from app.services.tool_service import tool_service  # noqa: E402


class StubAIService(AIService):
    def __init__(self, responses: list[AIResponse | None]):
        self.responses = responses
        self.request_count = 0

    @classmethod
    def remember_claimed_name(cls, db, session, user_text):
        return None

    @staticmethod
    def get_user_context(db, session):
        return "ผู้ใช้ปัจจุบัน:\nชื่อ: ทดสอบ\nrole: guest\nverified: false"

    @classmethod
    def get_data_context(cls, db, session):
        return {"lecturers": [], "rooms": [], "my_schedule": []}

    @classmethod
    def get_current_time_context(cls):
        return "เวลาทดสอบ"

    @staticmethod
    def get_history(db, session_id, limit=8):
        return []

    async def _request_gemini(self, system_prompt, contents):
        self.request_count += 1
        return self.responses.pop(0)


class TimeoutAIService(StubAIService):
    async def _request_gemini(self, system_prompt, contents):
        self.request_count += 1
        raise GeminiRequestTimeoutError


class AIArchitectureTests(unittest.TestCase):
    def test_direct_answer_calls_gemini_once(self):
        service = StubAIService(
            [AIResponse(response="สวัสดีครับ")]
        )

        reply = asyncio.run(
            service.generate_reply(
                object(),
                SimpleNamespace(id=1, user_id=None),
                "สวัสดี",
            )
        )

        self.assertEqual(reply, "สวัสดีครับ")
        self.assertEqual(service.request_count, 1)

    def test_context_answer_calls_gemini_once(self):
        service = StubAIService([AIResponse(response="ไม่พบข้อมูลครับ")])

        reply = asyncio.run(
            service.generate_reply(
                object(),
                SimpleNamespace(id=1, user_id=None),
                "ขอข้อมูล",
            )
        )

        self.assertEqual(reply, "ไม่พบข้อมูลครับ")
        self.assertEqual(service.request_count, 1)

    def test_gemini_timeout_returns_timeout_message(self):
        service = TimeoutAIService([])

        reply = asyncio.run(
            service.generate_reply(
                object(),
                SimpleNamespace(id=1, user_id=None),
                "ทดสอบ timeout",
            )
        )

        self.assertEqual(reply, service.TIMEOUT_RESPONSE)
        self.assertEqual(service.request_count, 1)

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(ValidationError):
            AIService._parse_response("ไม่ใช่ JSON")

        with self.assertRaises(ValidationError):
            AIService._parse_response(
                '{"response":"ok","extra":true}'
            )

    def test_prompt_contains_context_without_function_rules(self):
        prompt = AIService._build_system_prompt(
            "ผู้ใช้ปัจจุบัน:\nชื่อ: ทดสอบ\nrole: student\nverified: true",
            "เวลาทดสอบ",
            {
                "department": [{"content": "ปีการศึกษา 2536"}],
                "my_schedule": [{"subject": "AI"}],
            },
        )

        self.assertIn("ปีการศึกษา 2536", prompt)
        self.assertIn('"my_schedule"', prompt)
        self.assertNotIn("function_results", prompt)

    def test_guest_cannot_read_a_schedule(self):
        results = tool_service.execute_calls(
            object(),
            SimpleNamespace(id=1, user_id=None),
            [
                {
                    "name": "get_my_schedule",
                    "arguments": {"date": "2026-09-21"},
                }
            ],
        )

        self.assertEqual(
            results[0]["result"]["error"],
            "permission_denied",
        )

    def test_unknown_function_is_not_executed(self):
        results = tool_service.execute_calls(
            object(),
            SimpleNamespace(id=1, user_id=None),
            [{"name": "run_sql", "arguments": {"sql": "SELECT 1"}}],
        )

        self.assertEqual(
            results[0]["result"]["error"],
            "function_not_allowed",
        )

    def test_function_exception_is_hidden(self):
        results = tool_service.execute_calls(
            object(),
            SimpleNamespace(id=1, user_id=None),
            [{"name": "get_room_info", "arguments": {"query": "3201"}}],
        )

        self.assertEqual(
            results[0]["result"]["error"],
            "function_failed",
        )

    def test_department_search_returns_only_relevant_excerpts(self):
        result = tool_service._search_department_data(
            object(),
            SimpleNamespace(id=1, user_id=None),
            {"query": "ประวัติความเป็นมาของสาขา"},
        )

        self.assertGreater(len(result["items"]), 0)
        self.assertLessEqual(len(result["items"]), 3)
        self.assertLessEqual(
            sum(len(item["content"]) for item in result["items"]),
            4000,
        )


if __name__ == "__main__":
    unittest.main()
