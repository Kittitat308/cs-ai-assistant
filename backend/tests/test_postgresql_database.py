import unittest
from datetime import time
from pathlib import Path
from uuid import uuid4

import numpy as np
from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.models.face import FaceEmbedding
from app.models.room import Room
from app.models.schedule import ClassSchedule
from app.models.user import User


class PostgreSQLDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        environment = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
        database_url = environment.get("DATABASE_URL")

        if not database_url or not database_url.startswith("postgresql"):
            raise unittest.SkipTest("PostgreSQL DATABASE_URL is not configured")

        cls.engine = create_engine(database_url, pool_pre_ping=True)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_expected_schema_and_existing_embedding(self):
        inspector = inspect(self.engine)
        self.assertEqual(
            {
                "users",
                "face_embeddings",
                "class_schedules",
                "rooms",
                "lecturer_profiles",
            },
            set(inspector.get_table_names()),
        )

        with Session(self.engine) as session:
            embedding = session.scalars(
                session.query(FaceEmbedding).statement.limit(1)
            ).first()
            self.assertIsNotNone(embedding)
            self.assertEqual(len(embedding.embedding), 512)

    def test_crud_relationships_and_embedding_roundtrip(self):
        expected = np.linspace(-1.0, 1.0, 512, dtype=np.float32)
        suffix = uuid4().hex[:8]
        connection = self.engine.connect()
        transaction = connection.begin()

        try:
            with Session(bind=connection) as session:
                room = Room(
                    name=f"SC-TEST-{suffix}",
                    floor=2,
                    room_type="ห้องเรียน",
                    building="อาคารทดสอบ",
                )
                user = User(
                    name="ผู้ใช้ทดสอบ",
                    role="student",
                    student_id=f"99{int(suffix, 16) % 100000000:08d}",
                )
                session.add_all([room, user])
                session.flush()
                session.add(
                    FaceEmbedding(
                        user_id=user.id,
                        embedding=expected.tolist(),
                    )
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
                session.flush()

                stored = session.query(FaceEmbedding).filter_by(
                    user_id=user.id
                ).one()
                restored = np.asarray(stored.embedding, dtype=np.float32)
                self.assertEqual(restored.size, 512)
                self.assertTrue(np.array_equal(restored, expected))

                raw_dimensions = session.execute(
                    text(
                        "SELECT cardinality(embedding) FROM face_embeddings "
                        "WHERE user_id = :user_id"
                    ),
                    {"user_id": user.id},
                ).scalar_one()
                self.assertEqual(raw_dimensions, 512)
        finally:
            transaction.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()
