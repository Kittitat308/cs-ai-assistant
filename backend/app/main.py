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

    Base.metadata.create_all(
        bind=engine
    )

    # create_all ไม่เพิ่ม column ให้ table เดิม จึงรองรับฐานข้อมูล
    # ที่สร้าง class_schedules ก่อนมีตัวเลือกวันเรียน
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
