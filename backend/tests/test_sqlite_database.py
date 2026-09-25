import tempfile
import unittest
from datetime import time
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.face import FaceEmbedding
from app.models.room import Room
from app.models.schedule import ClassSchedule
from app.models.user import User


class SQLiteDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "test.db"
        self.engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_crud_relationships_and_embedding_roundtrip(self):
        expected_embedding = np.linspace(-1.0, 1.0, 512, dtype=np.float32)

        with Session(self.engine) as session:
            room = Room(
                name="SC-TEST",
                floor=2,
                room_type="ห้องเรียน",
                building="อาคารทดสอบ",
            )
            user = User(name="ผู้ใช้ทดสอบ", role="student", student_id="1234567890")
            session.add_all([room, user])
            session.flush()
            session.add(
                FaceEmbedding(user_id=user.id, embedding=expected_embedding.tolist())
            )
            session.add(
                ClassSchedule(
                    user_id=user.id,
                    room_id=room.id,
                    subject_name="วิชาทดสอบ",
                    course_code="CS101",
                    group_number=1,
                    meeting_index=1,
                    day_of_week="monday",
                    start_time=time(9, 0),
                    end_time=time(12, 0),
                )
            )
            session.commit()

            stored_face = session.query(FaceEmbedding).one()
            restored = np.asarray(stored_face.embedding, dtype=np.float32)
            self.assertEqual(restored.size, 512)
            self.assertTrue(np.array_equal(restored, expected_embedding))
            self.assertEqual(stored_face.user.name, "ผู้ใช้ทดสอบ")

            raw_blob = session.execute(
                text("SELECT embedding FROM face_embeddings")
            ).scalar_one()
            self.assertEqual(len(raw_blob), 2048)

            session.delete(room)
            session.commit()
            schedule = session.query(ClassSchedule).one()
            self.assertIsNone(schedule.room_id)

            session.delete(user)
            session.commit()
            self.assertEqual(session.query(FaceEmbedding).count(), 0)
            self.assertEqual(session.query(ClassSchedule).count(), 0)

            foreign_key_errors = session.execute(
                text("PRAGMA foreign_key_check")
            ).all()
            self.assertEqual(foreign_key_errors, [])

    def test_embedding_requires_exactly_512_values(self):
        with Session(self.engine) as session:
            user = User(name="ผู้ใช้ทดสอบ", role="guest")
            session.add(user)
            session.flush()
            session.add(FaceEmbedding(user_id=user.id, embedding=[0.0] * 511))

            with self.assertRaises(StatementError) as error:
                session.commit()

            self.assertIsInstance(error.exception.orig, ValueError)


if __name__ == "__main__":
    unittest.main()
