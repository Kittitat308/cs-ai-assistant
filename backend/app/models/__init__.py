# Import models เพื่อให้ SQLAlchemy รู้จัก table ทุกตัว
from app.models.conversation import ChatSession, Message, SessionProfile
from app.models.face import FaceEmbedding
from app.models.schedule import ClassSchedule
from app.models.user import User

__all__ = [
    "User",
    "FaceEmbedding",
    "ChatSession",
    "Message",
    "SessionProfile",
    "ClassSchedule",
]
