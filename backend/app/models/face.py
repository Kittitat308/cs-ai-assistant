from datetime import datetime

import numpy as np
from sqlalchemy import DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.database import Base


class Float32Embedding(TypeDecorator):
    """เก็บ ArcFace 512 มิติเป็น little-endian float32 BLOB (2048 bytes)."""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        if value is None:
            return None

        embedding = np.asarray(value, dtype="<f4")

        if embedding.ndim != 1 or embedding.size != 512:
            raise ValueError("Face embedding must contain exactly 512 values")

        return embedding.tobytes(order="C")

    def process_result_value(self, value, _dialect):
        if value is None:
            return None

        embedding = np.frombuffer(value, dtype="<f4")

        if embedding.size != 512:
            raise ValueError("Stored face embedding is not a 512-value float32 BLOB")

        return embedding.copy().tolist()


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
        Float32Embedding(length=512 * 4),
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
