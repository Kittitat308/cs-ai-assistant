from datetime import time

from sqlalchemy import ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ClassSchedule(Base):
    """รายวิชาและช่วงเวลาเรียนของผู้ใช้"""

    __tablename__ = "class_schedules"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    room_id: Mapped[int | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    subject_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    course_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    group_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    meeting_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    day_of_week: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="class_schedules",
    )

    room = relationship(
        "Room",
        back_populates="schedules",
    )
