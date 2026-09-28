import os
import unittest
from types import SimpleNamespace


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost/test",
)
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("ADMIN_TOKEN", "test")


from app.models.user import User  # noqa: E402
from app.routers.voice import _greeting_text  # noqa: E402


class FakeDatabase:
    def __init__(self, user):
        self.user = user

    def get(self, model, user_id):
        if model is User and self.user and self.user.id == user_id:
            return self.user
        return None


class VoiceGreetingTests(unittest.TestCase):
    def test_student_greeting_contains_name(self):
        database = FakeDatabase(
            SimpleNamespace(
                id=7,
                name="สมชาย ใจดี",
                role="student",
                is_active=True,
            )
        )

        self.assertEqual(
            _greeting_text(database, 7),
            "สวัสดีครับคุณ สมชาย ใจดี cs ai assistant พร้อมใช้งานแล้ว",
        )

    def test_guest_greeting_does_not_contain_name(self):
        self.assertEqual(
            _greeting_text(FakeDatabase(None), None),
            "สวัสดีครับ cs ai assistant พร้อมใช้งานแล้ว",
        )

    def test_non_student_or_lecturer_uses_guest_greeting(self):
        database = FakeDatabase(
            SimpleNamespace(
                id=9,
                name="ผู้ดูแล",
                role="admin",
                is_active=True,
            )
        )

        self.assertEqual(
            _greeting_text(database, 9),
            "สวัสดีครับ cs ai assistant พร้อมใช้งานแล้ว",
        )


if __name__ == "__main__":
    unittest.main()
