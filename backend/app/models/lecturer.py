from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LecturerProfile(Base):
    """ข้อมูลสาธารณะของอาจารย์ในสาขา"""

    __tablename__ = "lecturer_profiles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    academic_title: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    position: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    education: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="lecturer_profile",
    )
