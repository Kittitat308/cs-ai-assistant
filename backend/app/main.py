from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

# Import models ก่อน create_all
import app.models  # noqa: F401

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import (
    admin,
    face,
    health,
    registration,
    rooms,
    voice,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ทำงานตอน FastAPI startup

    ช่วงพัฒนา MVP ให้ SQLAlchemy
    สร้าง table ที่ยังไม่มีอัตโนมัติ

    ภายหลัง production เราจะเปลี่ยนเป็น Alembic migration
    """

    Base.metadata.create_all(bind=engine)

    # รองรับ PostgreSQL schema รุ่นเก่าโดยไม่ลบข้อมูลเดิม
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ADD COLUMN IF NOT EXISTS day_of_week "
                "VARCHAR(10) NOT NULL DEFAULT 'monday'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ALTER COLUMN day_of_week DROP DEFAULT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ADD COLUMN IF NOT EXISTS course_code "
                "VARCHAR(50) NOT NULL DEFAULT '-'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ALTER COLUMN course_code DROP DEFAULT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ADD COLUMN IF NOT EXISTS group_number "
                "INTEGER NOT NULL DEFAULT 1"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ALTER COLUMN group_number DROP DEFAULT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ADD COLUMN IF NOT EXISTS meeting_index "
                "INTEGER NOT NULL DEFAULT 1"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ALTER COLUMN meeting_index DROP DEFAULT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE class_schedules "
                "ADD COLUMN IF NOT EXISTS room_id "
                "INTEGER REFERENCES rooms(id) ON DELETE SET NULL"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_class_schedules_room_id ON class_schedules (room_id)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE users "
                "ADD COLUMN IF NOT EXISTS student_id VARCHAR(10)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE users "
                "ADD COLUMN IF NOT EXISTS email VARCHAR(255)"
            )
        )
        connection.execute(
            text(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'external_id') "
                "THEN "
                "UPDATE users SET student_id = external_id "
                "WHERE student_id IS NULL AND external_id ~ '^[0-9]{10}$'; "
                "UPDATE users SET email = LOWER(external_id) "
                "WHERE email IS NULL AND POSITION('@' IN external_id) > 1; "
                "ALTER TABLE users DROP COLUMN external_id; "
                "END IF; END $$"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_users_student_id ON users (student_id)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_users_email ON users (email)"
            )
        )
        connection.execute(
            text(
                "DROP TABLE IF EXISTS "
                "session_profiles, messages, chat_sessions CASCADE"
            )
        )

    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)


# --------------------------------------------
# CORS
# --------------------------------------------

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        settings.frontend_url,
    ],

    allow_credentials=True,

    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------
# Routers
# --------------------------------------------

app.include_router(
    health.router
)

app.include_router(
    face.router
)

app.include_router(
    voice.router
)

app.include_router(
    registration.router
)

app.include_router(
    rooms.router
)

app.include_router(
    admin.router
)


@app.get("/")
def root():
    """
    Root endpoint
    """

    return {
        "name": settings.app_name,
        "status": "running",
    }
