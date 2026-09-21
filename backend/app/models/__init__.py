# Import models เพื่อให้ SQLAlchemy รู้จัก table ทุกตัว
from app.models.conversation import ChatSession, Message, SessionProfile
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
    "ChatSession",
    "Message",
    "SessionProfile",
    "ClassSchedule",
]
