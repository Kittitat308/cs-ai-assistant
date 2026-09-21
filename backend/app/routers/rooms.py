from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.room import Room


router = APIRouter(
    prefix="/api/rooms",
    tags=["Rooms"],
)


@router.get("")
def list_rooms(db: Session = Depends(get_db)):
    rooms = (
        db.query(Room)
        .order_by(Room.building, Room.floor, Room.name)
        .all()
    )

    return [
        {
            "id": room.id,
            "name": room.name,
            "floor": room.floor,
            "room_type": room.room_type,
            "building": room.building,
        }
        for room in rooms
    ]
