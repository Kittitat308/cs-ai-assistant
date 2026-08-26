from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FaceEmbedding(Base):
    """
    เก็บ ArcFace embedding ของผู้ใช้

    หนึ่งคนสามารถมี embedding ได้หลายชุด
    เพื่อรองรับหลายมุมหน้าและสภาพแสง
    """

    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    # ArcFace embedding
    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    user = relationship(
        "User",
        back_populates="face_embeddings",
    )