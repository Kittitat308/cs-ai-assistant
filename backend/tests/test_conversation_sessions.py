import os
import unittest


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost/test",
)
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("ADMIN_TOKEN", "test")


from app.services.ai_service import AIService  # noqa: E402
from app.services.conversation_session_service import (  # noqa: E402
    HISTORY_MESSAGE_LIMIT,
    ConversationSessionService,
)


class ConversationSessionTests(unittest.TestCase):
    def setUp(self):
        self.service = ConversationSessionService()

    def test_same_identity_reuses_session(self):
        first = self.service.resolve_face_session(None, user_id=7)
        second = self.service.resolve_face_session(first.token, user_id=7)

        self.assertIs(first, second)

    def test_identity_change_starts_empty_session(self):
        first = self.service.resolve_face_session(None, user_id=7)
        self.service.append_exchange(first, "คำถามเดิม", "คำตอบเดิม")
        second = self.service.resolve_face_session(first.token, user_id=8)

        self.assertNotEqual(first.token, second.token)
        self.assertEqual(second.user_id, 8)
        self.assertEqual(second.history, [])

    def test_same_unknown_face_reuses_guest_session(self):
        first = self.service.resolve_face_session(
            None,
            user_id=None,
            face_embedding=[1.0, 0.0],
        )
        second = self.service.resolve_face_session(
            first.token,
            user_id=None,
            face_embedding=[0.99, 0.01],
        )

        self.assertIs(first, second)

    def test_new_unknown_face_starts_empty_guest_session(self):
        first = self.service.resolve_face_session(
            None,
            user_id=None,
            face_embedding=[1.0, 0.0],
        )
        self.service.append_exchange(first, "คำถามเดิม", "คำตอบเดิม")
        second = self.service.resolve_face_session(
            first.token,
            user_id=None,
            face_embedding=[0.0, 1.0],
        )

        self.assertNotEqual(first.token, second.token)
        self.assertIsNone(second.user_id)
        self.assertEqual(second.history, [])

    def test_missing_token_restarts_guest_without_stopping_voice(self):
        session = self.service.get_or_create_for_voice("reset-token")

        self.assertEqual(session.token, "reset-token")
        self.assertIsNone(session.user_id)
        self.assertEqual(session.history, [])

    def test_history_keeps_last_four_rounds(self):
        session = self.service.resolve_face_session(None, user_id=None)

        for index in range(6):
            self.service.append_exchange(
                session,
                f"user-{index}",
                f"assistant-{index}",
            )

        history = self.service.get_history(session)

        self.assertEqual(len(history), HISTORY_MESSAGE_LIMIT)
        self.assertEqual(history[0].content, "user-2")
        self.assertEqual(history[-1].content, "assistant-5")

    def test_guest_name_is_kept_in_memory(self):
        session = self.service.resolve_face_session(None, user_id=None)
        name = AIService.remember_claimed_name(
            object(),
            session,
            "ผมชื่อ สมชาย ใจดีครับ",
        )

        self.assertEqual(name, "สมชาย ใจดี")
        self.assertEqual(session.claimed_name, "สมชาย ใจดี")


if __name__ == "__main__":
    unittest.main()
