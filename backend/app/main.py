from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.services.stt_service import stt_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ทำงานตอน FastAPI startup

    ช่วงพัฒนา MVP ให้ SQLAlchemy
    สร้าง table ที่ยังไม่มีอัตโนมัติ

    ภายหลัง production เราจะเปลี่ยนเป็น Alembic migration
    """

    Base.metadata.create_all(bind=engine)
    await stt_service.warm_up()

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
