from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """
    ผู้ใช้ของระบบ

    role:
    - student
    - lecturer
    - admin
    - guest
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # รหัสนักศึกษา/รหัสบุคลากร
    external_id: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="guest",
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    # Face embeddings ของผู้ใช้
    face_embeddings = relationship(
        "FaceEmbedding",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    class_schedules = relationship(
        "ClassSchedule",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    lecturer_profile = relationship(
        "LecturerProfile",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
