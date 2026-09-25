# Import models เพื่อให้ SQLAlchemy รู้จัก table ทุกตัว
from app.models.face import FaceEmbedding
from app.models.lecturer import LecturerProfile
from app.models.room import Room
from app.models.schedule import ClassSchedule
from app.models.user import User

__all__ = [
    "User",
    "FaceEmbedding",
    "LecturerProfile",
    "Room",
    "ClassSchedule",
]
