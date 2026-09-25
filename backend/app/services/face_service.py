import cv2
import numpy as np
import onnxruntime as ort
from insightface.app import FaceAnalysis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.face import FaceEmbedding


class FaceService:
    """
    จัดการ Face Detection + Face Recognition

    InsightFace buffalo_l ประกอบด้วย model ที่ใช้
    detection และ ArcFace recognition
    """

    def __init__(self):
        # เลือก provider ที่ติดตั้งอยู่จริง เพื่อให้รันได้ทั้ง
        # เครื่องที่มี NVIDIA GPU และเครื่องที่ใช้ CPU เท่านั้น
        available_providers = ort.get_available_providers()
        providers = [
            provider
            for provider in (
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            )
            if provider in available_providers
        ]

        if not providers:
            raise RuntimeError(
                "ONNX Runtime ไม่มี execution provider ที่รองรับ"
            )

        self.app = FaceAnalysis(
            name=settings.face_model,
            providers=providers,
        )

        # เตรียม detector
        self.app.prepare(
            ctx_id=(
                0
                if "CUDAExecutionProvider" in providers
                else -1
            ),
            det_size=(
                settings.face_detection_size,
                settings.face_detection_size,
            ),
        )

    @staticmethod
    def decode_image(image_bytes: bytes) -> np.ndarray:
        """
        แปลง JPEG/PNG bytes ที่รับจาก browser
        เป็น OpenCV image
        """

        array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            array,
            cv2.IMREAD_COLOR,
        )

        if image is None:
            raise ValueError("ไม่สามารถอ่านภาพได้")

        return image

    def get_single_face_embedding(
        self,
        image_bytes: bytes,
    ) -> np.ndarray:
        """
        หาใบหน้าจากภาพ

        ระบบกำหนดให้ต้องมี 1 หน้าเท่านั้น
        เพราะกำลังระบุตัวผู้ใช้ที่ยืนหน้าระบบ
        """

        image = self.decode_image(image_bytes)

        faces = self.app.get(image)

        if len(faces) == 0:
            raise ValueError("NO_FACE")

        if len(faces) > 1:
            raise ValueError("MULTIPLE_FACES")

        face = faces[0]

        # normed_embedding ถูก normalize มาแล้ว
        embedding = np.asarray(
            face.normed_embedding,
            dtype=np.float32,
        )

        return embedding

    def get_primary_face_embedding(
        self,
        image_bytes: bytes,
    ) -> np.ndarray:
        """เลือกใบหน้าที่มีกรอบใหญ่ที่สุดสำหรับการรู้จำหน้ากล้อง"""

        image = self.decode_image(image_bytes)
        faces = self.app.get(image)

        if len(faces) == 0:
            raise ValueError("NO_FACE")

        primary_face = max(
            faces,
            key=lambda face: max(
                0.0,
                float(face.bbox[2] - face.bbox[0]),
            ) * max(
                0.0,
                float(face.bbox[3] - face.bbox[1]),
            ),
        )

        return np.asarray(
            primary_face.normed_embedding,
            dtype=np.float32,
        )

    @staticmethod
    def cosine_similarity(
        embedding_a: np.ndarray,
        embedding_b: np.ndarray,
    ) -> float:
        """
        คำนวณ cosine similarity ระหว่างใบหน้าสองชุด
        """

        a = embedding_a / np.linalg.norm(embedding_a)
        b = embedding_b / np.linalg.norm(embedding_b)

        return float(np.dot(a, b))

    def recognize(
        self,
        db: Session,
        image_bytes: bytes,
    ):
        user, similarity, _embedding = self.recognize_with_embedding(
            db,
            image_bytes,
        )
        return user, similarity

    def recognize_with_embedding(
        self,
        db: Session,
        image_bytes: bytes,
    ):
        """
        เปรียบเทียบใบหน้ากับ PostgreSQL และคืน embedding สำหรับติดตาม Guest
        """

        input_embedding = self.get_primary_face_embedding(
            image_bytes
        )

        stored_faces = db.query(FaceEmbedding).all()

        best_face = None
        best_similarity = -1.0

        for stored in stored_faces:
            stored_embedding = np.asarray(
                stored.embedding,
                dtype=np.float32,
            )

            similarity = self.cosine_similarity(
                input_embedding,
                stored_embedding,
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_face = stored

        # ไม่มีข้อมูลใบหน้าในระบบเลย
        if best_face is None:
            return None, 0.0, input_embedding

        # similarity ต่ำกว่า threshold
        if best_similarity < settings.face_threshold:
            return None, best_similarity, input_embedding

        return best_face.user, best_similarity, input_embedding


# สร้าง service เพียงครั้งเดียว
face_service = FaceService()
