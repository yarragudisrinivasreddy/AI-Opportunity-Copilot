import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.core import privacy
from app.core.local_privacy import BlackoutRedactor, StaticFaceDetector
from app.core.privacy import Box, SanitizationError
from tests.conftest import make_jpeg


def region_std(data: bytes, box: Box) -> float:
    img = np.array(Image.open(io.BytesIO(data)).convert("L"), dtype=float)
    h, w = img.shape
    return float(img[int(box.y0 * h):int(box.y1 * h), int(box.x0 * w):int(box.x1 * w)].std())


def test_face_region_is_blurred_and_rest_untouched():
    box = Box(0.2, 0.2, 0.4, 0.5)
    original = make_jpeg()
    result = privacy.sanitize_image(original, StaticFaceDetector([box]), None)
    assert result.findings.faces_blurred == 1
    assert region_std(result.data, box) < 0.5 * region_std(original, box)
    far = Box(0.7, 0.7, 0.95, 0.95)
    assert abs(region_std(result.data, far) - region_std(original, far)) < 10


def test_exif_is_stripped():
    img = Image.open(io.BytesIO(make_jpeg()))
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"
    exif[0x0132] = "2026:10:05 10:00:00"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    assert b"SecretCamera" in buf.getvalue()
    out = privacy.sanitize_image(buf.getvalue(), StaticFaceDetector(), None)
    assert b"SecretCamera" not in out.data
    assert len(Image.open(io.BytesIO(out.data)).getexif()) == 0


def test_pii_redactor_applied_and_reported():
    redactor = BlackoutRedactor([Box(0.5, 0.5, 0.9, 0.9)])
    result = privacy.sanitize_image(make_jpeg(), StaticFaceDetector(), redactor)
    assert result.findings.pii_redaction_applied and result.findings.pii_regions_masked == 1
    assert "face(s) blurred" in result.findings.summary()


def test_large_images_are_downscaled():
    big = make_jpeg(size=(2400, 1800))
    out = privacy.sanitize_image(big, StaticFaceDetector(), None)
    assert max(Image.open(io.BytesIO(out.data)).size) <= privacy.MAX_SIDE


@pytest.mark.parametrize("bad", [b"", b"not an image", b"GIF89a" + b"\x00" * 50, b"\xff\xd8\xff" + b"\x00" * 20])
def test_bad_or_unsupported_files_rejected(bad):
    with pytest.raises(SanitizationError):
        privacy.sanitize_image(bad, StaticFaceDetector(), None)


def test_oversize_rejected():
    with pytest.raises(SanitizationError):
        privacy.sanitize_image(b"\xff\xd8\xff" + b"0" * (privacy.MAX_IMAGE_BYTES + 1), StaticFaceDetector(), None)


def test_detector_failure_rejects_media_not_passes_it_through():
    class Boom:
        def detect(self, b):
            raise RuntimeError("vision unavailable")

    with pytest.raises(SanitizationError):
        privacy.sanitize_image(make_jpeg(), Boom(), None)


def test_redactor_failure_rejects_media():
    class Boom:
        def redact(self, b):
            raise RuntimeError("dlp unavailable")

    with pytest.raises(SanitizationError):
        privacy.sanitize_image(make_jpeg(), StaticFaceDetector(), Boom())


def make_video(path, seconds=3, fps=5) -> bytes:
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for i in range(seconds * fps):
        frame = np.full((48, 64, 3), (i * 7) % 255, dtype=np.uint8)
        w.write(frame)
    w.release()
    return path.read_bytes()


def test_video_sampled_at_one_frame_per_second(tmp_path):
    data = make_video(tmp_path / "v.mp4", seconds=3, fps=5)
    frames = privacy.sample_frames(data)
    assert 2 <= len(frames) <= 4
    assert all(f[:3] == b"\xff\xd8\xff" for f in frames)


def test_video_too_long_rejected(tmp_path):
    data = make_video(tmp_path / "long.mp4", seconds=40, fps=2)
    with pytest.raises(SanitizationError):
        privacy.sample_frames(data)


def test_video_garbage_rejected():
    with pytest.raises(SanitizationError):
        privacy.sample_frames(b"\x00\x00\x00\x18ftypmp42" + b"junk" * 20)
