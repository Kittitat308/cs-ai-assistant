import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChatSession(Base):
    """
    Session การสนทนา

    token ถูกสร้างโดย backend หลัง face recognition
    frontend ไม่สามารถเลือก user_id เองได้
    """

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        default=lambda: uuid.uuid4().hex,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


class SessionProfile(Base):
    """ชื่อที่ผู้ใช้แจ้งเองระหว่างการสนทนา (ยังไม่ยืนยันตัวตน)"""

    __tablename__ = "session_profiles"

    session_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chat_sessions.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    claimed_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Message(Base):
    """
    เก็บ conversation memory

    role:
    - user
    - assistant
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chat_sessions.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
