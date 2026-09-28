from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """
    Base class ของ SQLAlchemy models ทั้งหมด
    """

    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


# Session สำหรับติดต่อ PostgreSQL
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    """
    FastAPI dependency สำหรับเปิด/ปิด database session
    อัตโนมัติในแต่ละ request
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
