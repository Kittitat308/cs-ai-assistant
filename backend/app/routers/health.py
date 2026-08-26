from fastapi import APIRouter


router = APIRouter(
    prefix="/api",
    tags=["Health"],
)


@router.get("/health")
def health():
    """
    ใช้ตรวจว่า Backend ทำงานอยู่หรือไม่
    """

    return {
        "status": "ok",
        "service": "CS AI Assistant",
    }