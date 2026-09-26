import os
import unittest


os.environ.setdefault("DATABASE_PATH", ":memory:")
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

    def test_history_keeps_last_three_rounds(self):
        session = self.service.resolve_face_session(None, user_id=None)

        for index in range(6):
            self.service.append_exchange(
                session,
                f"user-{index}",
                f"assistant-{index}",
            )

        history = self.service.get_history(session)

        self.assertEqual(len(history), HISTORY_MESSAGE_LIMIT)
        self.assertEqual(history[0].content, "user-3")
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

    def test_student_verification_starts_with_zero_failures(self):
        session = self.service.resolve_face_session(
            None,
            user_id=7,
            user_role="student",
        )

        self.assertTrue(session.verify_user)
        self.assertEqual(session.verify_fail_count, 0)

    def test_verified_user_becomes_guest_after_three_failures(self):
        session = self.service.resolve_face_session(
            None,
            user_id=7,
            user_role="lecturer",
        )

        first = self.service.resolve_no_face_session(session.token)
        self.assertIs(first, session)
        self.assertEqual(first.verify_fail_count, 1)

        second = self.service.resolve_face_session(
            session.token,
            user_id=None,
            face_embedding=[1.0, 0.0],
        )
        self.assertIs(second, session)
        self.assertEqual(second.verify_fail_count, 2)

        third = self.service.resolve_no_face_session(session.token)

        self.assertIsNotNone(third)
        self.assertNotEqual(third.token, session.token)
        self.assertIsNone(third.user_id)
        self.assertFalse(third.verify_user)
        self.assertTrue(third.verification_failed)
        self.assertFalse(session.verify_user)

    def test_same_verified_user_resets_failure_count(self):
        session = self.service.resolve_face_session(
            None,
            user_id=7,
            user_role="student",
        )
        self.service.resolve_no_face_session(session.token)

        matched = self.service.resolve_face_session(
            session.token,
            user_id=7,
            user_role="student",
        )

        self.assertIs(matched, session)
        self.assertEqual(matched.verify_fail_count, 0)
        self.assertTrue(matched.verify_user)

    def test_different_student_switches_session_immediately(self):
        first = self.service.resolve_face_session(
            None,
            user_id=7,
            user_role="student",
        )

        second = self.service.resolve_face_session(
            first.token,
            user_id=8,
            user_role="student",
        )

        self.assertNotEqual(second.token, first.token)
        self.assertEqual(second.user_id, 8)
        self.assertTrue(second.verify_user)
        self.assertEqual(second.verify_fail_count, 0)

    def test_registered_guest_does_not_switch_verified_user_immediately(self):
        student = self.service.resolve_face_session(
            None,
            user_id=7,
            user_role="student",
        )

        result = self.service.resolve_face_session(
            student.token,
            user_id=20,
            user_role="guest",
        )

        self.assertIs(result, student)
        self.assertEqual(result.user_id, 7)
        self.assertEqual(result.verify_fail_count, 1)


if __name__ == "__main__":
    unittest.main()
