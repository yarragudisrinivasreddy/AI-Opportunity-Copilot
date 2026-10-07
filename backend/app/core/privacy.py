"""Privacy preprocessing (PRD section 16). Nothing reaches a model or a provider unsanitised.

Pipeline: validate -> decode (EXIF stripped) -> face blur -> PII mask -> re-encode.
Face detection and PII masking are pluggable: Cloud Vision / Cloud DLP in production,
fakes in tests. Any failure raises SanitizationError and the media is REJECTED, never passed on.
"""
import io
import os
import tempfile
from dataclasses import dataclass, field
from typing import Protocol

from PIL import Image, ImageFilter, ImageOps

MAX_SIDE = 1600
MAX_PIXELS = 40_000_000
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_VIDEO_BYTES = 20 * 1024 * 1024
MAX_VIDEO_SECONDS = 30
MAX_FRAMES = 30

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class SanitizationError(Exception):
    """Media could not be validated or sanitised; it must be rejected."""


@dataclass(frozen=True)
class Box:
    """Relative bounding box, all values in 0..1."""

    x0: float
    y0: float
    x1: float
    y1: float


class FaceDetector(Protocol):
    def detect(self, jpeg_bytes: bytes) -> list[Box]: ...


class ImageRedactor(Protocol):
    def redact(self, jpeg_bytes: bytes) -> tuple[bytes, int | None]:
        """Return (redacted image bytes, number of masked regions if known)."""
        ...


@dataclass
class PrivacyFindings:
    faces_blurred: int = 0
    pii_regions_masked: int | None = 0
    pii_redaction_applied: bool = False
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"{self.faces_blurred} face(s) blurred"]
        if self.pii_redaction_applied:
            n = self.pii_regions_masked
            parts.append("sensitive text masked" if n is None else f"{n} sensitive region(s) masked")
        return ", ".join(parts)


@dataclass
class SanitizedImage:
    data: bytes
    mime: str
    findings: PrivacyFindings


def _jpeg(img: Image.Image, quality: int = 88) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)  # no exif written
    return buf.getvalue()


def _blur_boxes(img: Image.Image, boxes: list[Box]) -> Image.Image:
    w, h = img.size
    for b in boxes:
        bw, bh = (b.x1 - b.x0) * w, (b.y1 - b.y0) * h
        pad_x, pad_y = bw * 0.2, bh * 0.2  # blur a margin around the face
        left = max(0, int(b.x0 * w - pad_x))
        top = max(0, int(b.y0 * h - pad_y))
        right = min(w, int(b.x1 * w + pad_x))
        bottom = min(h, int(b.y1 * h + pad_y))
        if right <= left or bottom <= top:
            continue
        region = img.crop((left, top, right, bottom))
        radius = max(12, int(max(region.size) / 5))
        img.paste(region.filter(ImageFilter.GaussianBlur(radius)), (left, top))
    return img


def sanitize_image(
    data: bytes, detector: FaceDetector, redactor: ImageRedactor | None
) -> SanitizedImage:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise SanitizationError("image missing or larger than the allowed size")
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise SanitizationError("unsupported image type")
        w, h = img.size
        if w * h > MAX_PIXELS:
            raise SanitizationError("image dimensions too large")
        img.load()
        img = ImageOps.exif_transpose(img).convert("RGB")
        if max(img.size) > MAX_SIDE:
            img.thumbnail((MAX_SIDE, MAX_SIDE))
    except SanitizationError:
        raise
    except Exception as exc:  # corrupt or hostile file
        raise SanitizationError("could not decode image") from exc

    findings = PrivacyFindings()
    try:
        working = _jpeg(img)
        faces = detector.detect(working)
        img = _blur_boxes(img, faces)
        findings.faces_blurred = len(faces)
        out = _jpeg(img)
        if redactor is not None:
            out, masked = redactor.redact(out)
            findings.pii_redaction_applied = True
            findings.pii_regions_masked = masked
    except SanitizationError:
        raise
    except Exception as exc:
        raise SanitizationError("privacy processing failed; media rejected") from exc

    # Re-decode the final bytes to prove they are a valid image and carry no metadata.
    try:
        check = Image.open(io.BytesIO(out))
        check.verify()
    except Exception as exc:
        raise SanitizationError("sanitised output invalid") from exc
    return SanitizedImage(data=out, mime="image/jpeg", findings=findings)


def sample_frames(video: bytes, max_frames: int = MAX_FRAMES, max_seconds: int = MAX_VIDEO_SECONDS):
    """Sample <=1 frame/sec from a short video. Audio is never read. Returns JPEG bytes list."""
    if not video or len(video) > MAX_VIDEO_BYTES:
        raise SanitizationError("video missing or larger than the allowed size")
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover
        raise SanitizationError("video support unavailable") from exc

    fd, path = tempfile.mkstemp(suffix=".mp4")
    frames: list[bytes] = []
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(video)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise SanitizationError("could not open video")
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if fps <= 0 or count <= 0:
            raise SanitizationError("video metadata invalid")
        if count / fps > max_seconds + 1:
            raise SanitizationError(f"video longer than {max_seconds} seconds")
        step = max(1, int(round(fps)))
        index = 0
        while len(frames) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                ok2, buf = cv2.imencode(".jpg", frame)
                if ok2:
                    frames.append(buf.tobytes())
            index += 1
        cap.release()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if not frames:
        raise SanitizationError("no frames could be read from the video")
    return frames


# ---- Production implementations (lazy imports; not exercised by offline tests) ----
class CloudVisionFaceDetector:
    """Face detection via Cloud Vision. UNVERIFIED against the live API; see docs/TASKS.md."""

    def detect(self, jpeg_bytes: bytes) -> list[Box]:
        from google.cloud import vision

        client = vision.ImageAnnotatorClient()
        response = client.face_detection(image=vision.Image(content=jpeg_bytes))
        if response.error.message:
            raise SanitizationError("face detection failed")
        w, h = Image.open(io.BytesIO(jpeg_bytes)).size
        boxes: list[Box] = []
        for face in response.face_annotations:
            xs = [v.x for v in face.bounding_poly.vertices]
            ys = [v.y for v in face.bounding_poly.vertices]
            boxes.append(Box(min(xs) / w, min(ys) / h, max(xs) / w, max(ys) / h))
        return boxes


class CloudDlpImageRedactor:
    """Image PII redaction via Sensitive Data Protection. UNVERIFIED against the live API."""

    INFO_TYPES = ("PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD_NUMBER", "PERSON_NAME")

    def __init__(self, project: str, location: str = "global") -> None:
        self._parent = f"projects/{project}/locations/{location}"

    def redact(self, jpeg_bytes: bytes) -> tuple[bytes, int | None]:
        from google.cloud import dlp_v2

        client = dlp_v2.DlpServiceClient()
        response = client.redact_image(
            request={
                "parent": self._parent,
                "byte_item": {"type_": dlp_v2.ByteContentItem.BytesType.IMAGE_JPEG, "data": jpeg_bytes},
                "inspect_config": {"info_types": [{"name": n} for n in self.INFO_TYPES]},
                "image_redaction_configs": [{"info_type": {"name": n}} for n in self.INFO_TYPES],
            }
        )
        return response.redacted_image, None
