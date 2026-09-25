import threading
import uuid
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta


HISTORY_MESSAGE_LIMIT = 8
SESSION_TTL = timedelta(hours=2)


@dataclass(slots=True)
class ConversationMessage:
    role: str
    content: str


@dataclass(slots=True)
class ConversationSession:
    token: str
    user_id: int | None = None
    claimed_name: str | None = None
    face_embedding: tuple[float, ...] | None = None
    history: list[ConversationMessage] = field(default_factory=list)
    last_seen_at: datetime = field(default_factory=datetime.utcnow)


class ConversationSessionService:
    """เก็บ session สนทนาชั่วคราวใน Python โดยไม่พึ่งตารางฐานข้อมูล"""

    def __init__(self):
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = threading.RLock()

    def resolve_face_session(
        self,
        token: str | None,
        user_id: int | None,
        face_embedding: list[float] | tuple[float, ...] | None = None,
        face_threshold: float = 0.45,
    ) -> ConversationSession:
        """ใช้ session เดิมเมื่อ identity เดิมยังอยู่ มิฉะนั้นเริ่ม session ใหม่"""

        with self._lock:
            self._cleanup()
            current = self._sessions.get(token or "")

            if current is not None:
                same_known_user = (
                    user_id is not None
                    and current.user_id == user_id
                )
                same_guest = (
                    user_id is None
                    and current.user_id is None
                    and self._same_face(
                        current.face_embedding,
                        face_embedding,
                        face_threshold,
                    )
                )

                if same_known_user or same_guest:
                    current.last_seen_at = datetime.utcnow()

                    if face_embedding is not None:
                        current.face_embedding = tuple(face_embedding)

                    return current

            return self._create(
                user_id=user_id,
                face_embedding=face_embedding,
            )

    def get_or_create_for_voice(self, token: str) -> ConversationSession:
        """token ที่หายหลัง reset/restart ต้องไม่ทำให้ voice pipeline หยุด"""

        clean_token = token.strip()[:128]

        with self._lock:
            self._cleanup()
            session = self._sessions.get(clean_token)

            if session is None:
                session = self._create(
                    user_id=None,
                    token=(clean_token[:128] or None),
                )

            session.last_seen_at = datetime.utcnow()
            return session

    def append_exchange(
        self,
        session: ConversationSession,
        user_text: str,
        assistant_text: str,
    ) -> None:
        with self._lock:
            session.history.extend(
                [
                    ConversationMessage(role="user", content=user_text),
                    ConversationMessage(
                        role="assistant",
                        content=assistant_text,
                    ),
                ]
            )
            session.history[:] = session.history[-HISTORY_MESSAGE_LIMIT:]
            session.last_seen_at = datetime.utcnow()

    def get_history(
        self,
        session: ConversationSession,
        limit: int = HISTORY_MESSAGE_LIMIT,
    ) -> list[ConversationMessage]:
        with self._lock:
            return list(session.history[-limit:])

    def _create(
        self,
        user_id: int | None,
        token: str | None = None,
        face_embedding: list[float] | tuple[float, ...] | None = None,
    ) -> ConversationSession:
        session_token = token or uuid.uuid4().hex
        session = ConversationSession(
            token=session_token,
            user_id=user_id,
            face_embedding=(
                tuple(face_embedding)
                if face_embedding is not None
                else None
            ),
        )
        self._sessions[session_token] = session
        return session

    @staticmethod
    def _same_face(
        first: tuple[float, ...] | None,
        second: list[float] | tuple[float, ...] | None,
        threshold: float,
    ) -> bool:
        if first is None or second is None or len(first) != len(second):
            return False

        first_norm = math.sqrt(sum(value * value for value in first))
        second_norm = math.sqrt(sum(value * value for value in second))

        if first_norm == 0 or second_norm == 0:
            return False

        similarity = sum(
            left * right
            for left, right in zip(first, second)
        ) / (first_norm * second_norm)
        return similarity >= threshold

    def _cleanup(self) -> None:
        cutoff = datetime.utcnow() - SESSION_TTL
        expired = [
            token
            for token, session in self._sessions.items()
            if session.last_seen_at < cutoff
        ]

        for token in expired:
            self._sessions.pop(token, None)


conversation_session_service = ConversationSessionService()
