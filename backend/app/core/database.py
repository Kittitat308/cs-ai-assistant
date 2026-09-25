from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """
    Base class ของ SQLAlchemy models ทั้งหมด
    """

    pass


BACKEND_ROOT = Path(__file__).resolve().parents[2]
configured_database_path = settings.database_path.strip()

if configured_database_path == ":memory:":
    database_path = None
    database_url = "sqlite+pysqlite:///:memory:"
else:
    database_path = Path(configured_database_path).expanduser()

    if not database_path.is_absolute():
        database_path = BACKEND_ROOT / database_path

    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

# SQLite ต้องเปิด foreign_keys ทุก connection เพื่อให้ ON DELETE ทำงานเหมือนเดิม
engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Session สำหรับติดต่อ SQLite
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
