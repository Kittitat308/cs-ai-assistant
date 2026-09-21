from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Room(Base):
    """ข้อมูลห้องที่สาขาวิทยาการคอมพิวเตอร์ใช้งาน"""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    floor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    room_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    building: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    schedules = relationship(
        "ClassSchedule",
        back_populates="room",
    )
