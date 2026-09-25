"""ย้ายข้อมูล CS AI Assistant จาก PostgreSQL ไป SQLite แบบไม่แก้ source."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from dotenv import dotenv_values
from sqlalchemy import create_engine, event, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import Base  # noqa: E402
from app.models.face import FaceEmbedding  # noqa: E402
from app.models.lecturer import LecturerProfile  # noqa: E402
from app.models.room import Room  # noqa: E402
from app.models.schedule import ClassSchedule  # noqa: E402
from app.models.user import User  # noqa: E402


TABLE_MODELS = (
    User,
    Room,
    LecturerProfile,
    ClassSchedule,
    FaceEmbedding,
)


def get_source_url(explicit_url: str | None) -> str:
    if explicit_url:
        source_url = explicit_url
    else:
        environment = dotenv_values(BACKEND_ROOT / ".env")
        source_url = (
            environment.get("POSTGRES_SOURCE_URL")
            or environment.get("DATABASE_URL")
            or ""
        )

    if not source_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise ValueError(
            "ไม่พบ PostgreSQL source URL: ใช้ --source-url หรือกำหนด "
            "POSTGRES_SOURCE_URL ใน backend/.env"
        )

    return source_url


def create_sqlite_engine(target_path: Path):
    target_engine = create_engine(
        f"sqlite+pysqlite:///{target_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(target_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return target_engine


def read_source_rows(source_connection) -> dict[str, list[dict]]:
    rows_by_table = {}

    for model in TABLE_MODELS:
        table = model.__table__
        column_names = [column.name for column in table.columns]
        columns_sql = ", ".join(f'"{name}"' for name in column_names)
        result = source_connection.execute(
            text(f'SELECT {columns_sql} FROM "{table.name}" ORDER BY id')
        )
        rows_by_table[table.name] = [dict(row) for row in result.mappings()]

    return rows_by_table


def verify_migration(source_rows, target_engine) -> dict:
    report = {"tables": {}, "face_embeddings": {}}

    with target_engine.connect() as connection:
        foreign_key_errors = connection.exec_driver_sql(
            "PRAGMA foreign_key_check"
        ).all()

        if foreign_key_errors:
            raise RuntimeError(f"SQLite foreign key errors: {foreign_key_errors}")

        for model in TABLE_MODELS:
            table_name = model.__tablename__
            source_table_rows = source_rows[table_name]
            target_table_rows = [
                dict(row)
                for row in connection.execute(
                    model.__table__.select().order_by(model.__table__.c.id)
                ).mappings()
            ]
            source_ids = [row["id"] for row in source_table_rows]
            target_ids = [row["id"] for row in target_table_rows]

            if source_ids != target_ids:
                raise RuntimeError(f"Primary keys ไม่ตรงกันในตาราง {table_name}")

            for source_row, target_row in zip(
                source_table_rows,
                target_table_rows,
                strict=True,
            ):
                for column_name, source_value in source_row.items():
                    if column_name == "embedding":
                        continue

                    if target_row[column_name] != source_value:
                        raise RuntimeError(
                            f"ข้อมูล {table_name}.{column_name} id={source_row['id']} "
                            "ไม่ตรงกับ PostgreSQL"
                        )

            report["tables"][table_name] = {
                "postgresql": len(source_ids),
                "sqlite": len(target_ids),
                "row_values_match": True,
            }

        target_embeddings = {
            row.id: bytes(row.embedding)
            for row in connection.execute(
                text("SELECT id, embedding FROM face_embeddings ORDER BY id")
            )
        }

    maximum_float32_error = 0.0

    for source_row in source_rows["face_embeddings"]:
        source_values = np.asarray(source_row["embedding"], dtype=np.float64)

        if source_values.ndim != 1 or source_values.size != 512:
            raise RuntimeError(
                f"PostgreSQL embedding id={source_row['id']} ไม่ครบ 512 ค่า"
            )

        expected_float32 = np.asarray(source_values, dtype="<f4")
        stored_blob = target_embeddings[source_row["id"]]
        restored_float32 = np.frombuffer(stored_blob, dtype="<f4")

        if len(stored_blob) != 512 * 4 or restored_float32.size != 512:
            raise RuntimeError(
                f"SQLite embedding id={source_row['id']} มีขนาดไม่ถูกต้อง"
            )

        if stored_blob != expected_float32.tobytes(order="C"):
            raise RuntimeError(
                f"SQLite embedding id={source_row['id']} เกิด corruption"
            )

        maximum_float32_error = max(
            maximum_float32_error,
            float(np.max(np.abs(source_values - restored_float32.astype(np.float64)))),
        )

    report["face_embeddings"] = {
        "count": len(source_rows["face_embeddings"]),
        "dimensions_each": 512,
        "storage": "BLOB little-endian float32",
        "bytes_each": 512 * 4,
        "maximum_source_to_float32_error": maximum_float32_error,
        "blob_roundtrip_exact": True,
    }
    report["foreign_key_check"] = "passed"
    return report


def migrate(source_url: str, target_path: Path) -> dict:
    target_path = target_path.resolve()

    if target_path.exists():
        raise FileExistsError(
            f"ไฟล์ SQLite มีอยู่แล้ว จึงไม่เขียนทับ: {target_path}"
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_sqlite_engine(target_path)

    try:
        with source_engine.connect() as source_connection:
            source_transaction = source_connection.begin()
            source_connection.execute(text("SET TRANSACTION READ ONLY"))

            try:
                source_rows = read_source_rows(source_connection)
                Base.metadata.create_all(bind=target_engine)

                with target_engine.begin() as target_connection:
                    for model in TABLE_MODELS:
                        table_name = model.__tablename__
                        rows = source_rows[table_name]

                        if rows:
                            target_connection.execute(model.__table__.insert(), rows)

                report = verify_migration(source_rows, target_engine)
            finally:
                source_transaction.rollback()

        report["sqlite_path"] = str(target_path)
        return report
    except Exception:
        target_engine.dispose()

        if target_path.exists():
            target_path.unlink()

        raise
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", help="PostgreSQL URL ต้นทาง")
    parser.add_argument(
        "--target",
        type=Path,
        default=BACKEND_ROOT / "data" / "cs_ai_assistant.db",
        help="ไฟล์ SQLite ปลายทาง (ต้องยังไม่มีไฟล์)",
    )
    args = parser.parse_args()
    report = migrate(get_source_url(args.source_url), args.target)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
