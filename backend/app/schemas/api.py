from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    """
    Request สำหรับ Admin สร้างนักศึกษา/อาจารย์
    """

    name: str
    student_id: str | None = None
    email: str | None = None

    role: str = Field(
        pattern="^(student|lecturer|admin)$",
    )


class UserResponse(BaseModel):
    id: int
    student_id: str | None
    email: str | None
    name: str
    role: str


class FaceRecognitionResponse(BaseModel):
    status: str

    recognized: bool = False

    user_id: int | None = None
    name: str | None = None
    role: str | None = None

    similarity: float | None = None

    session_token: str | None = None
