"""Local (non-Google) privacy components for development and tests.

OpenCVFaceDetector uses a Haar cascade: DEV ONLY. Its recall is much lower than Cloud Vision,
so never quote its numbers as the product's privacy performance (see docs/EVALUATION.md E7).
"""
import io

from PIL import Image

from app.core.privacy import Box


class OpenCVFaceDetector:
    def detect(self, jpeg_bytes: bytes) -> list[Box]:
        import cv2
        import numpy as np

        img = Image.open(io.BytesIO(jpeg_bytes)).convert("L")
        w, h = img.size
        gray = np.array(img)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(24, 24))
        return [Box(x / w, y / h, (x + fw) / w, (y + fh) / h) for (x, y, fw, fh) in faces]


class StaticFaceDetector:
    """Returns fixed boxes. For tests."""

    def __init__(self, boxes: list[Box] | None = None) -> None:
        self.boxes = boxes or []

    def detect(self, jpeg_bytes: bytes) -> list[Box]:
        return list(self.boxes)


class BlackoutRedactor:
    """Masks fixed boxes in solid black. For tests."""

    def __init__(self, boxes: list[Box] | None = None) -> None:
        self.boxes = boxes or []

    def redact(self, jpeg_bytes: bytes) -> tuple[bytes, int | None]:
        img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        w, h = img.size
        for b in self.boxes:
            img.paste((0, 0, 0), (int(b.x0 * w), int(b.y0 * h), int(b.x1 * w), int(b.y1 * h)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return buf.getvalue(), len(self.boxes)
